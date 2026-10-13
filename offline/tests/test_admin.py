"""Step 2 tests: the admin routes (password, localhost only, order of steps)."""
import pytest
from fastapi.testclient import TestClient

from app import config, db, tokens
from app.main import app

PASSWORD = "correct horse battery"
RIGHT = {"X-Admin-Password": PASSWORD}
ADMIN_ROUTES = [
    ("post", "/admin/open"),
    ("post", "/admin/close"),
    ("post", "/admin/reveal"),
    ("get", "/admin/status"),
]


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.sqlite")
    monkeypatch.setattr(config, "ADMIN_PASSWORD", PASSWORD)
    return config.DB_PATH


@pytest.fixture
def laptop(temp_db):
    """A client that looks like it is on the server laptop itself."""
    with TestClient(app, client=("127.0.0.1", 50000)) as c:
        yield c


@pytest.fixture
def phone(temp_db):
    """A client that looks like a voter's phone on the Wi-Fi."""
    with TestClient(app, client=("192.168.10.57", 50000)) as c:
        yield c


def call(client, method, path, headers=None):
    return getattr(client, method)(path, headers=headers or {})


# ---- who may use the admin routes ------------------------------------------

@pytest.mark.parametrize("method, path", ADMIN_ROUTES)
def test_a_phone_is_refused_even_with_the_right_password(phone, method, path):
    response = call(phone, method, path, RIGHT)
    assert response.status_code == 403
    assert db.get_state() == "IDLE"


@pytest.mark.parametrize("method, path", ADMIN_ROUTES)
def test_no_password_header_is_refused(laptop, method, path):
    assert call(laptop, method, path).status_code == 401


@pytest.mark.parametrize("method, path", ADMIN_ROUTES)
def test_wrong_password_is_refused_and_nothing_changes(laptop, method, path):
    response = call(laptop, method, path, {"X-Admin-Password": "wrong"})
    assert response.status_code == 401
    assert db.get_state() == "IDLE"


def test_the_password_in_the_web_address_does_not_work(laptop):
    # If the password were accepted in the URL it could end up in logs.
    assert laptop.post(f"/admin/open?password={PASSWORD}").status_code == 401
    assert laptop.post(f"/admin/open?x_admin_password={PASSWORD}").status_code == 401
    assert db.get_state() == "IDLE"


@pytest.mark.parametrize("method, path", ADMIN_ROUTES)
def test_admin_is_switched_off_when_no_password_is_set(temp_db, monkeypatch, method, path):
    monkeypatch.setattr(config, "ADMIN_PASSWORD", "")
    with TestClient(app, client=("127.0.0.1", 50000)) as laptop:
        # Even an empty password header must not get in.
        assert call(laptop, method, path, {"X-Admin-Password": ""}).status_code == 503
        assert call(laptop, method, path).status_code == 503
    assert db.get_state() == "IDLE"


def test_a_phone_learns_nothing_when_admin_is_switched_off(temp_db, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_PASSWORD", "")
    with TestClient(app, client=("192.168.10.57", 50000)) as phone:
        assert phone.post("/admin/open").status_code == 403  # same answer as always


def test_the_ipv6_localhost_address_counts_as_the_laptop(temp_db):
    with TestClient(app, client=("::1", 50000)) as laptop:
        assert laptop.post("/admin/open", headers=RIGHT).status_code == 200


# ---- the steps ------------------------------------------------------------

def test_open_close_reveal_in_order(laptop):
    for path, expected in (("/admin/open", "OPEN"), ("/admin/close", "CLOSED"),
                           ("/admin/reveal", "RESULTS")):
        response = laptop.post(path, headers=RIGHT)
        assert response.status_code == 200
        assert response.json() == {"state": expected}
        assert db.get_state() == expected
        assert laptop.get("/api/state").json() == {"state": expected}


@pytest.mark.parametrize(
    "start, path",
    [
        ("IDLE", "/admin/close"),      # nothing to close yet
        ("IDLE", "/admin/reveal"),
        ("OPEN", "/admin/open"),       # pressed Open twice
        ("OPEN", "/admin/reveal"),     # must Close first
        ("CLOSED", "/admin/open"),     # no re-opening after Close
        ("RESULTS", "/admin/close"),
        ("RESULTS", "/admin/reveal"),
    ],
)
def test_a_step_out_of_order_gives_409_and_changes_nothing(laptop, start, path):
    with db.connect() as conn:
        conn.execute("UPDATE config SET value = ? WHERE key = 'state'", (start,))
    response = laptop.post(path, headers=RIGHT)
    assert response.status_code == 409
    assert db.get_state() == start


# ---- status -----------------------------------------------------------------

def test_status_shows_only_totals(laptop):
    db.add_candidate("Alpha")
    plain = [tokens.generate_token() for _ in range(4)]
    db.add_token_hashes([tokens.hash_token(t) for t in plain])
    laptop.post("/admin/open", headers=RIGHT)
    laptop.post("/api/vote", json={"token": plain[0], "candidate_id": 1})

    body = laptop.get("/admin/status", headers=RIGHT).json()
    assert body == {"state": "OPEN", "tokens_issued": 4, "votes_cast": 1}
    # Exactly these three keys: nothing per candidate (SPEC A7).


# ---- the real thing, end to end -----------------------------------------------

def test_voting_only_works_between_open_and_close(laptop):
    db.add_candidate("Alpha")
    plain = [tokens.generate_token() for _ in range(3)]
    db.add_token_hashes([tokens.hash_token(t) for t in plain])

    def vote(t):
        return laptop.post("/api/vote", json={"token": t, "candidate_id": 1}).status_code

    assert vote(plain[0]) == 403                       # before Open
    laptop.post("/admin/open", headers=RIGHT)
    assert vote(plain[0]) == 200                       # while open
    laptop.post("/admin/close", headers=RIGHT)
    assert vote(plain[1]) == 403                       # after Close
    assert db.count_votes() == 1
    assert db.token_is_usable(tokens.hash_token(plain[1]))  # not burned by the refused vote
