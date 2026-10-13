import sqlite3
import uuid
from pathlib import Path

from app import config


def connect():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    schema = (Path(__file__).parent / "schema.sql").read_text()
    with connect() as conn:
        conn.executescript(schema)
        conn.execute(
            "INSERT OR IGNORE INTO config (key, value) VALUES ('state', 'IDLE')"
        )


def get_state():
    with connect() as conn:
        row = conn.execute("SELECT value FROM config WHERE key = 'state'").fetchone()
    return row[0]


# The election only moves forward, one step at a time (SPEC section 5):
#   IDLE -> OPEN -> CLOSED -> RESULTS
# Built from config.STATES so the order is written down in only one place.
NEXT_STATE = dict(zip(config.STATES, config.STATES[1:]))
PREVIOUS_STATE = {new: old for old, new in NEXT_STATE.items()}


class BadTransition(Exception):
    """The requested state change is not allowed right now."""


def change_state(new_state):
    """Move the election to new_state. Only the very next step is allowed.

    Raises BadTransition if the move is not allowed: skipping a step, going
    backwards, repeating the current state, or an unknown state name.

    Why a single UPDATE: "set it to new_state, but only if it is still
    old_state" is one all-or-nothing step in SQLite. If the admin double-clicks
    Open, or two people press it at once, exactly one of them wins and the
    other gets BadTransition. We never read first and write later, because
    in between someone else could have changed it.
    """
    old_state = PREVIOUS_STATE.get(new_state)
    if old_state is None:
        # IDLE has no previous step (nothing can go back to it), and an
        # unknown name is not a state at all.
        raise BadTransition(f"cannot move to {new_state!r}")

    with connect() as conn:
        changed = conn.execute(
            "UPDATE config SET value = ? WHERE key = 'state' AND value = ?",
            (new_state, old_state),
        ).rowcount
    if changed != 1:
        raise BadTransition(
            f"cannot move to {new_state}: the election is {get_state()}, not {old_state}"
        )
    return new_state


def add_candidate(name):
    """Add one candidate and return the new candidate's id."""
    with connect() as conn:
        cursor = conn.execute("INSERT INTO candidates (name) VALUES (?)", (name,))
        return cursor.lastrowid


def list_candidates():
    """Return all candidates as a list of {"id": ..., "name": ...}, in id order."""
    with connect() as conn:
        rows = conn.execute("SELECT id, name FROM candidates ORDER BY id").fetchall()
    return [{"id": row[0], "name": row[1]} for row in rows]


def count_tokens():
    """How many tokens (hashes) are stored."""
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM tokens").fetchone()[0]


def add_token_hashes(hashes):
    """Store token hashes, all unused. Either all of them are saved or none."""
    with connect() as conn:
        conn.executemany(
            "INSERT INTO tokens (token_hash, used) VALUES (?, 0)",
            [(h,) for h in hashes],
        )


def token_is_usable(token_hash):
    """True if this hash exists and has not been used yet. Changes nothing."""
    with connect() as conn:
        row = conn.execute(
            "SELECT used FROM tokens WHERE token_hash = ?", (token_hash,)
        ).fetchone()
    return row is not None and row[0] == 0


# Possible answers from cast_vote().
VOTE_OK = "ok"
VOTE_NOT_OPEN = "not_open"
VOTE_BAD_TOKEN = "bad_token"


def cast_vote(token_hash, candidate_id):
    """Burn the token and save the vote in ONE all-or-nothing transaction.

    Returns VOTE_OK, VOTE_NOT_OPEN or VOTE_BAD_TOKEN.

    Why one transaction: if the token were burned and the server then crashed
    before the vote was saved, a voter would lose their vote. If the vote were
    saved first, a crash could let the same token vote twice. In one
    transaction either both happen or neither does.

    ANONYMITY: the vote row gets a fresh random id and the candidate, nothing
    else. Nothing here links the token to the vote, and nothing is logged.
    """
    conn = connect()
    # isolation_level = None: Python will not start transactions behind our back,
    # so the BEGIN / COMMIT / ROLLBACK below are exactly what runs.
    conn.isolation_level = None
    try:
        # IMMEDIATE takes the write lock now, so two votes can never be
        # processed at the same moment: they queue up and go one by one.
        conn.execute("BEGIN IMMEDIATE")
        try:
            # Checked inside the transaction so a vote cannot slip in
            # after the admin pressed Close.
            state = conn.execute(
                "SELECT value FROM config WHERE key = 'state'"
            ).fetchone()[0]
            if state != "OPEN":
                conn.execute("ROLLBACK")
                return VOTE_NOT_OPEN

            # "AND used = 0" is what makes double voting impossible: the second
            # try finds no unused row, so zero rows change.
            burned = conn.execute(
                "UPDATE tokens SET used = 1 WHERE token_hash = ? AND used = 0",
                (token_hash,),
            ).rowcount
            if burned != 1:
                conn.execute("ROLLBACK")
                return VOTE_BAD_TOKEN

            conn.execute(
                "INSERT INTO votes (id, candidate_id) VALUES (?, ?)",
                (str(uuid.uuid4()), candidate_id),
            )
            conn.execute("COMMIT")
            return VOTE_OK
        except BaseException:
            # Any surprise (for example an unknown candidate): undo everything,
            # so the token is NOT burned, then let the error continue.
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()


def candidate_exists(candidate_id):
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM candidates WHERE id = ?", (candidate_id,)
        ).fetchone()
    return row is not None
