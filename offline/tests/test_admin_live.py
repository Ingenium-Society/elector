"""Stage 4 tests for guarded admin controls and live updates."""
import pytest
from fastapi.testclient import TestClient

from app import config, db
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.sqlite")
    monkeypatch.setenv("ADMIN_PASSWORD", "test-secret")
    # The admin routes deliberately reject requests not originating on loopback.
    with TestClient(app, client=("127.0.0.1", 50000)) as test_client:
        yield test_client


def admin(client, action, password="test-secret"):
    headers = {}
    if password is not None:
        headers["X-Admin-Password"] = password
    return client.post(f"/admin/{action}", headers=headers)


def test_admin_state_machine_and_results(client):
    db.add_candidate("Alpha")
    db.add_candidate("Beta")
    db.add_candidate("Gamma")

    assert admin(client, "open").json() == {"state": "OPEN"}
    assert admin(client, "close").json() == {"state": "CLOSED"}
    response = admin(client, "reveal")
    assert response.status_code == 200
    assert response.json()["state"] == "RESULTS"
    assert response.json()["results"] == [
        {"id": 1, "name": "Alpha", "votes": 0},
        {"id": 2, "name": "Beta", "votes": 0},
        {"id": 3, "name": "Gamma", "votes": 0},
    ]


@pytest.mark.parametrize("action", ["open", "close", "reveal"])
def test_admin_transition_rejects_wrong_state(client, action):
    response = admin(client, action)
    assert response.status_code == 409
    assert db.get_state() == "IDLE"


def test_admin_routes_require_password(client):
    assert admin(client, "open", password=None).status_code == 401
    assert admin(client, "open", password="wrong").status_code == 401
    assert db.get_state() == "IDLE"


def test_admin_status_returns_aggregate_counts_only(client):
    response = client.get("/admin/status", headers={"X-Admin-Password": "test-secret"})
    assert response.status_code == 200
    assert response.json() == {"state": "IDLE", "votes_cast": 0, "tokens_issued": 0}


def test_live_websocket_starts_with_state_and_aggregate_counts(client):
    with client.websocket_connect("/ws") as websocket:
        payload = websocket.receive_json()
        assert payload == {"state": "IDLE", "votes_cast": 0, "tokens_issued": 0}
        assert "candidate" not in str(payload).lower()
        assert "token" not in str(payload).lower()
        admin(client, "open")
        update = websocket.receive_json()
        assert update["state"] == "OPEN"
        assert update["votes_cast"] == 0
        assert update["tokens_issued"] == 0
