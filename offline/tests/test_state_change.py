"""Step 1 tests: db.change_state() only allows the next step, one direction."""
import threading

import pytest

from app import config, db


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.sqlite")
    db.init_db()
    return config.DB_PATH


def force_state(state):
    """Set the state directly, to prepare a test (not through change_state)."""
    with db.connect() as conn:
        conn.execute("UPDATE config SET value = ? WHERE key = 'state'", (state,))


# ---- the allowed path ------------------------------------------------------

def test_full_path_works_and_is_saved(temp_db):
    assert db.get_state() == "IDLE"
    for step in ("OPEN", "CLOSED", "RESULTS"):
        assert db.change_state(step) == step
        assert db.get_state() == step


# ---- everything else is refused, and nothing changes ------------------------

@pytest.mark.parametrize(
    "start, target",
    [
        ("IDLE", "CLOSED"),     # skipping OPEN
        ("IDLE", "RESULTS"),    # skipping two steps
        ("OPEN", "RESULTS"),    # skipping CLOSED
        ("OPEN", "IDLE"),       # going back
        ("CLOSED", "OPEN"),     # no re-opening after Close
        ("CLOSED", "IDLE"),
        ("RESULTS", "CLOSED"),  # going back
        ("RESULTS", "OPEN"),
        ("IDLE", "IDLE"),       # staying in the same state
        ("OPEN", "OPEN"),       # pressing Open twice
        ("RESULTS", "RESULTS"),
        ("IDLE", "STARTED"),    # not a real state
        ("OPEN", ""),
    ],
)
def test_other_moves_are_refused_and_state_is_unchanged(temp_db, start, target):
    force_state(start)
    with pytest.raises(db.BadTransition):
        db.change_state(target)
    assert db.get_state() == start


def test_the_state_survives_a_restart(temp_db):
    db.change_state("OPEN")
    # A "restart" is a brand new connection to the same file; init_db() must not reset it.
    db.init_db()
    assert db.get_state() == "OPEN"


# ---- two admins pressing at the same moment ---------------------------------

def test_many_simultaneous_opens_only_one_wins(temp_db):
    results = []

    def press_open():
        try:
            db.change_state("OPEN")
            results.append("won")
        except db.BadTransition:
            results.append("refused")

    threads = [threading.Thread(target=press_open) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count("won") == 1
    assert results.count("refused") == 19
    assert db.get_state() == "OPEN"


# ---- closing really stops voting -------------------------------------------

def test_a_vote_is_refused_after_close(temp_db):
    db.add_candidate("Alpha")
    db.add_token_hashes(["abc"])
    db.change_state("OPEN")
    db.change_state("CLOSED")
    assert db.cast_vote("abc", 1) == db.VOTE_NOT_OPEN
    assert db.token_is_usable("abc")  # the token was not burned
