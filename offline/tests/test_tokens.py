"""Step 1 tests: token helpers and scripts/generate_tokens.py."""
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from app import db, tokens

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "generate_tokens.py"
SLIP_FORMAT = re.compile(r"^[A-Z2-9]{4}-[A-Z2-9]{4}$")


# ---- app/tokens.py ---------------------------------------------------------

def test_alphabet_has_no_lookalike_characters():
    for bad in "01OIL":
        assert bad not in tokens.ALPHABET


def test_generated_token_has_the_slip_format():
    for _ in range(200):
        token = tokens.generate_token()
        assert SLIP_FORMAT.match(token), token
        assert all(c in tokens.ALPHABET for c in token.replace("-", ""))


def test_generated_tokens_differ():
    assert len({tokens.generate_token() for _ in range(500)}) == 500


def test_normalize_ignores_case_spaces_and_hyphens():
    for typed in ("K7M2-9QXP", "k7m2-9qxp", "k7m2 9qxp", " K7M29QXP ", "K7-M2 9Q-XP"):
        assert tokens.normalize_token(typed) == "K7M29QXP"


def test_hash_is_sha256_of_the_normalized_token():
    expected = hashlib.sha256(b"K7M29QXP").hexdigest()
    assert tokens.hash_token("K7M2-9QXP") == expected
    assert tokens.hash_token("k7m2 9qxp") == expected


# ---- scripts/generate_tokens.py -------------------------------------------

def run_script(db_file, out_file, *args):
    """Run the script against a temporary database and output file."""
    env = dict(os.environ, VOTING_DB=str(db_file))
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args, "--out", str(out_file)],
        capture_output=True, text=True, env=env, cwd=SCRIPT.parent.parent,
    )


def stored_hashes(db_file, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "DB_PATH", db_file)
    with db.connect() as conn:
        return [row for row in conn.execute("SELECT token_hash, used FROM tokens")]


def test_script_makes_tokens_and_stores_only_hashes(tmp_path, monkeypatch):
    db_file, out_file = tmp_path / "t.sqlite", tmp_path / "slips.txt"
    result = run_script(db_file, out_file, "25")
    assert result.returncode == 0, result.stderr

    readable = out_file.read_text().split()
    assert len(readable) == 25 and len(set(readable)) == 25
    assert all(SLIP_FORMAT.match(t) for t in readable)

    rows = stored_hashes(db_file, monkeypatch)
    assert sorted(h for h, _ in rows) == sorted(tokens.hash_token(t) for t in readable)
    assert all(used == 0 for _, used in rows)

    # The plain tokens must not be anywhere in the database file.
    raw = db_file.read_bytes()
    for t in readable:
        assert t.replace("-", "").encode() not in raw


def test_script_does_not_print_the_tokens(tmp_path):
    out_file = tmp_path / "slips.txt"
    result = run_script(tmp_path / "t.sqlite", out_file, "5")
    for t in out_file.read_text().split():
        assert t not in result.stdout and t not in result.stderr


def test_script_refuses_to_run_twice(tmp_path):
    db_file = tmp_path / "t.sqlite"
    assert run_script(db_file, tmp_path / "a.txt", "5").returncode == 0
    second = run_script(db_file, tmp_path / "b.txt", "5")
    assert second.returncode != 0
    assert "already exist" in second.stderr
    assert not (tmp_path / "b.txt").exists()


def test_script_never_overwrites_an_existing_file(tmp_path):
    out_file = tmp_path / "slips.txt"
    out_file.write_text("keep me")
    result = run_script(tmp_path / "t.sqlite", out_file, "5")
    assert result.returncode != 0
    assert out_file.read_text() == "keep me"


@pytest.mark.parametrize("count", ["0", "-3", "1001"])
def test_script_rejects_silly_counts(tmp_path, count):
    result = run_script(tmp_path / "t.sqlite", tmp_path / "s.txt", count)
    assert result.returncode != 0
    assert not (tmp_path / "s.txt").exists()
