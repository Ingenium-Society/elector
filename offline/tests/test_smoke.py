"""Stage 1 smoke tests.

A "smoke test" is a very small check that the basics work: the database can be
created, the server starts, and /api/state answers. If these fail, nothing
else in the project can be trusted yet.

Every test uses a temporary database file, so these tests never touch
the real election database in offline/data/.
"""
import os
import sqlite3
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from app import config, db
from app.main import app


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point the app at a brand-new empty database for one test."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.sqlite")
    return config.DB_PATH


@pytest.fixture
def client(temp_db):
    # Using TestClient as a "with" block makes FastAPI run its startup code,
    # which is where init_db() creates the tables.
    with TestClient(app) as c:
        yield c


def column_names(table):
    """Return the list of column names of a table in the test database."""
    with db.connect() as conn:
        return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


# ---- Database schema -------------------------------------------------------

def test_init_db_creates_all_tables(temp_db):
    db.init_db()
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    tables = {row[0] for row in rows}
    assert {"config", "candidates", "tokens", "votes"} <= tables


def test_state_starts_as_idle(temp_db):
    db.init_db()
    assert db.get_state() == "IDLE"


def test_init_db_twice_does_not_reset_state(temp_db):
    # The server may restart during the election. A restart must keep the state.
    db.init_db()
    with db.connect() as conn:
        conn.execute("UPDATE config SET value = 'OPEN' WHERE key = 'state'")
    db.init_db()
    assert db.get_state() == "OPEN"


# ---- Anonymity guards (AGENTS.md rule 1) -----------------------------------

def test_votes_table_has_only_id_and_candidate_id(temp_db):
    # If someone adds a timestamp, token reference, or IP column to votes,
    # this test fails on purpose. Do not "fix" it by editing the test.
    db.init_db()
    assert column_names("votes") == ["id", "candidate_id"]


def test_tokens_table_has_no_time_or_vote_link(temp_db):
    # Tokens keep only a hash and a used flag, so a token can never be
    # matched to a vote by time or by reference.
    db.init_db()
    assert column_names("tokens") == ["token_hash", "used"]


def test_vote_for_unknown_candidate_is_rejected(temp_db):
    # The database itself refuses a ballot for a candidate that does not exist.
    db.init_db()
    with db.connect() as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO votes (id, candidate_id) VALUES ('abc', 999)"
            )


# ---- Server ----------------------------------------------------------------

def test_api_state_returns_idle(client):
    response = client.get("/api/state")
    assert response.status_code == 200
    assert response.json() == {"state": "IDLE"}


def test_api_state_follows_the_database(client):
    with db.connect() as conn:
        conn.execute("UPDATE config SET value = 'CLOSED' WHERE key = 'state'")
    assert client.get("/api/state").json() == {"state": "CLOSED"}


def test_voter_page_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "School Election" in response.text


def test_voter_page_uses_no_internet_links(client):
    # AGENTS.md rule 5: the voting network has no internet,
    # so the page must not load anything from outside the laptop.
    html = client.get("/").text
    assert "http://" not in html
    assert "https://" not in html


# ---- Settings (must match docs/SPEC.md) ------------------------------------

def test_states_match_the_spec():
    assert config.STATES == ("IDLE", "OPEN", "CLOSED", "RESULTS")


def test_default_database_is_election_sqlite():
    # Checked in a fresh Python process so the VOTING_DB value of the
    # test machine cannot change the answer.
    code = "from app import config; print(config.DB_PATH.name)"
    env = {k: v for k, v in os.environ.items() if k != "VOTING_DB"}
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env=env
    )
    assert result.stdout.strip() == "election.sqlite"


def test_voting_db_env_var_overrides_the_path(tmp_path):
    import os
    target = tmp_path / "other.sqlite"
    code = "from app import config; print(config.DB_PATH)"
    env = dict(os.environ, VOTING_DB=str(target))
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env=env
    )
    assert result.stdout.strip() == str(target)
