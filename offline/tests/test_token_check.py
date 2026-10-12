"""Step 2 tests: POST /api/token/check (stateless pre-check)."""
import pytest
from fastapi.testclient import TestClient

from app import config, db, tokens
from app.main import app


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.sqlite")
    return config.DB_PATH


@pytest.fixture
def client(temp_db):
    with TestClient(app) as c:
        yield c


def set_state(state):
    with db.connect() as conn:
        conn.execute("UPDATE config SET value = ? WHERE key = 'state'", (state,))


@pytest.fixture
def token(client):
    """One real, unused token stored in the test database."""
    t = tokens.generate_token()
    db.add_token_hashes([tokens.hash_token(t)])
    return t


def check(client, text):
    return client.post("/api/token/check", json={"token": text})


def test_valid_token_is_accepted(client, token):
    response = check(client, token)
    assert response.status_code == 200
    assert response.json() == {"valid": True}


def test_unknown_token_is_not_valid(client, token):
    assert check(client, "AAAA-AAAA").json() == {"valid": False}


@pytest.mark.parametrize("junk", ["", "   ", "hello", "A" * 50, "????-????"])
def test_junk_is_simply_not_valid(client, token, junk):
    response = check(client, junk)
    assert response.status_code == 200
    assert response.json() == {"valid": False}


def test_typing_style_does_not_matter(client, token):
    typed = token.lower().replace("-", " ")
    assert check(client, typed).json() == {"valid": True}


def test_check_does_not_burn_the_token(client, token):
    for _ in range(3):
        assert check(client, token).json() == {"valid": True}
    with db.connect() as conn:
        assert conn.execute("SELECT used FROM tokens").fetchone()[0] == 0


def test_used_token_looks_the_same_as_an_unknown_one(client, token):
    with db.connect() as conn:
        conn.execute("UPDATE tokens SET used = 1")
    assert check(client, token).json() == {"valid": False}


def test_works_while_voting_is_open(client, token):
    set_state("OPEN")
    assert check(client, token).json() == {"valid": True}


@pytest.mark.parametrize("state", ["CLOSED", "RESULTS"])
def test_refused_after_voting_ends(client, token, state):
    set_state(state)
    assert check(client, token).status_code == 403


def test_missing_or_oversized_token_field_is_rejected(client):
    assert client.post("/api/token/check", json={}).status_code == 422
    assert check(client, "A" * 65).status_code == 422


def test_check_writes_nothing_to_the_database(client, token):
    # Stateless: nothing may record who checked or when.
    with db.connect() as conn:
        before = conn.execute("SELECT * FROM tokens").fetchall()
        votes_before = conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0]
    check(client, token)
    with db.connect() as conn:
        assert conn.execute("SELECT * FROM tokens").fetchall() == before
        assert conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0] == votes_before
