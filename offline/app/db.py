import sqlite3
import uuid
from pathlib import Path

from app import config


def connect():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=10)
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


def transition_state(expected, target):
    """Change state only if it is the expected state; never skip a stage."""
    with connect() as conn:
        cursor = conn.execute(
            "UPDATE config SET value = ? WHERE key = 'state' AND value = ?",
            (target, expected),
        )
        return cursor.rowcount == 1


def election_counts():
    """Return aggregate counts only; never associate a token with a ballot."""
    with connect() as conn:
        votes = conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0]
        issued = conn.execute("SELECT COUNT(*) FROM tokens").fetchone()[0]
    return {"votes_cast": votes, "tokens_issued": issued}


def result_totals():
    """Return candidate totals for the post-election reveal screen only."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT candidates.id, candidates.name, COUNT(votes.id)
            FROM candidates
            LEFT JOIN votes ON votes.candidate_id = candidates.id
            GROUP BY candidates.id, candidates.name
            ORDER BY candidates.id
            """
        ).fetchall()
    return [{"id": row[0], "name": row[1], "votes": row[2]} for row in rows]


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
    conn.isolation_level = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            state = conn.execute(
                "SELECT value FROM config WHERE key = 'state'"
            ).fetchone()[0]
            if state != "OPEN":
                conn.execute("ROLLBACK")
                return VOTE_NOT_OPEN

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
