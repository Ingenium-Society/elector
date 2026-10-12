"""Step 3 tests: POST /api/vote and the atomic vote transaction."""
import threading

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
def election(client):
    """Three candidates, five unused tokens, voting OPEN. Returns the plain tokens."""
    for name in ("Alpha", "Beta", "Gamma"):
        db.add_candidate(name)
    plain = [tokens.generate_token() for _ in range(5)]
    db.add_token_hashes([tokens.hash_token(t) for t in plain])
    set_state("OPEN")
    return plain


def vote(client, token, candidate_id=1):
    return client.post("/api/vote", json={"token": token, "candidate_id": candidate_id})


def all_votes():
    with db.connect() as conn:
        return conn.execute("SELECT id, candidate_id FROM votes").fetchall()


def token_rows():
    with db.connect() as conn:
        return dict(conn.execute("SELECT token_hash, used FROM tokens").fetchall())


# ---- the happy path ---------------------------------------------------------

def test_valid_vote_is_counted_and_token_is_burned(client, election):
    response = vote(client, election[0], candidate_id=2)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert [c for _, c in all_votes()] == [2]
    assert token_rows()[tokens.hash_token(election[0])] == 1


def test_other_tokens_stay_unused(client, election):
    vote(client, election[0])
    unused = [h for h, used in token_rows().items() if used == 0]
    assert len(unused) == 4


def test_token_typed_differently_still_works(client, election):
    assert vote(client, election[0].lower().replace("-", " ")).status_code == 200


def test_check_then_vote_flow(client, election):
    # SPEC section 12: check a token while IDLE, then vote after Open.
    set_state("IDLE")
    assert client.post("/api/token/check", json={"token": election[0]}).json() == {"valid": True}
    assert token_rows()[tokens.hash_token(election[0])] == 0   # the check burned nothing
    set_state("OPEN")
    assert vote(client, election[0]).status_code == 200


# ---- one token, one vote ----------------------------------------------------

def test_double_vote_is_rejected(client, election):
    assert vote(client, election[0], 1).status_code == 200
    second = vote(client, election[0], 2)
    assert second.status_code == 400
    assert len(all_votes()) == 1            # still only the first vote


def test_two_devices_pass_the_check_but_only_one_votes(client, election):
    token = election[0]
    assert client.post("/api/token/check", json={"token": token}).json()["valid"] is True
    assert client.post("/api/token/check", json={"token": token}).json()["valid"] is True
    assert vote(client, token).status_code == 200
    assert vote(client, token).status_code == 400
    assert len(all_votes()) == 1


def test_many_threads_with_one_token_give_exactly_one_vote(client, election):
    # 20 phones send the same token at the same instant.
    results, start = [], threading.Barrier(20)
    h = tokens.hash_token(election[0])

    def attempt():
        start.wait()
        results.append(db.cast_vote(h, 1))

    threads = [threading.Thread(target=attempt) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count(db.VOTE_OK) == 1
    assert results.count(db.VOTE_BAD_TOKEN) == 19
    assert len(all_votes()) == 1


def test_every_token_can_vote_once_and_totals_reconcile(client, election):
    for i, t in enumerate(election):
        assert vote(client, t, candidate_id=(i % 3) + 1).status_code == 200
    assert len(all_votes()) == 5
    assert sum(token_rows().values()) == 5            # tokens used = votes cast


# ---- rejected votes must not burn tokens -----------------------------------

def test_unknown_token_is_rejected(client, election):
    assert vote(client, "AAAA-AAAA").status_code == 400
    assert all_votes() == []


def test_unknown_candidate_is_rejected_and_token_not_burned(client, election):
    assert vote(client, election[0], candidate_id=999).status_code == 400
    assert all_votes() == []
    assert token_rows()[tokens.hash_token(election[0])] == 0   # voter can still vote


def test_database_rolls_back_if_the_vote_cannot_be_saved(client, election):
    # Skip the server's own candidate check and hit the database directly:
    # the insert fails, so the token must NOT stay burned (all or nothing).
    h = tokens.hash_token(election[0])
    with pytest.raises(Exception):
        db.cast_vote(h, 999)
    assert token_rows()[h] == 0
    assert all_votes() == []


@pytest.mark.parametrize("state", ["IDLE", "CLOSED", "RESULTS"])
def test_vote_refused_unless_open_and_token_not_burned(client, election, state):
    set_state(state)
    assert vote(client, election[0]).status_code == 403
    assert all_votes() == []
    assert token_rows()[tokens.hash_token(election[0])] == 0


def test_vote_refused_inside_the_transaction_if_closed(client, election):
    # The race the server-side pre-check cannot catch: Close arrives between
    # the check and the transaction. The transaction checks the state itself.
    set_state("CLOSED")
    assert db.cast_vote(tokens.hash_token(election[0]), 1) == db.VOTE_NOT_OPEN
    assert all_votes() == []


@pytest.mark.parametrize("body", [
    {}, {"token": "x"}, {"candidate_id": 1},
    {"token": "x", "candidate_id": "one"},
    {"token": "A" * 65, "candidate_id": 1},
])
def test_malformed_requests_are_rejected(client, election, body):
    assert client.post("/api/vote", json=body).status_code == 422
    assert all_votes() == []


# ---- anonymity (AGENTS.md rule 1) -------------------------------------------

def test_vote_row_has_only_a_random_id_and_the_candidate(client, election):
    vote(client, election[0], 3)
    (vote_id, candidate_id), = all_votes()
    assert candidate_id == 3
    assert len(vote_id) == 36 and vote_id.count("-") == 4      # random UUID text


def test_nothing_in_votes_mentions_the_token(client, election):
    vote(client, election[0], 1)
    h = tokens.hash_token(election[0])
    plain = election[0].replace("-", "")
    with db.connect() as conn:
        dump = " ".join(str(v) for row in conn.execute("SELECT * FROM votes") for v in row)
    assert h not in dump and plain not in dump


def test_vote_ids_are_all_different(client, election):
    for t in election:
        vote(client, t, 1)
    ids = [i for i, _ in all_votes()]
    assert len(set(ids)) == 5


def test_response_gives_nothing_that_identifies_the_vote(client, election):
    assert vote(client, election[0], 1).json() == {"ok": True}
