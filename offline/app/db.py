import sqlite3
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
