"""Stage 2 tests: candidates in the database and GET /api/candidates."""
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config, db
from app.main import app

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "add_candidates.py"


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.sqlite")
    return config.DB_PATH


@pytest.fixture
def client(temp_db):
    with TestClient(app) as c:
        yield c


def run_script(db_file, *names):
    """Run scripts/add_candidates.py against a temporary database."""
    env = dict(os.environ, VOTING_DB=str(db_file))
    return subprocess.run(
        [sys.executable, str(SCRIPT), *names],
        capture_output=True, text=True, env=env, cwd=SCRIPT.parent.parent,
    )


def test_no_candidates_at_first(client):
    assert client.get("/api/candidates").json() == {"candidates": []}


def test_added_candidates_are_returned_in_order(client):
    for name in ("Alpha", "Beta", "Gamma"):
        db.add_candidate(name)
    names = [c["name"] for c in client.get("/api/candidates").json()["candidates"]]
    assert names == ["Alpha", "Beta", "Gamma"]


def test_candidates_have_ids(client):
    db.add_candidate("Alpha")
    candidate = client.get("/api/candidates").json()["candidates"][0]
    assert isinstance(candidate["id"], int)


def test_script_adds_three_candidates(tmp_path):
    result = run_script(tmp_path / "s.sqlite", "Alpha", "Beta", "Gamma")
    assert result.returncode == 0, result.stderr
    assert "Alpha, Beta, Gamma" in result.stdout


def test_script_refuses_wrong_number_of_names(tmp_path):
    result = run_script(tmp_path / "s.sqlite", "Alpha", "Beta")
    assert result.returncode != 0
    assert "exactly 3" in result.stderr


def test_script_refuses_duplicate_names(tmp_path):
    result = run_script(tmp_path / "s.sqlite", "Alpha", "alpha", "Gamma")
    assert result.returncode != 0
    assert "same name" in result.stderr


def test_script_refuses_to_run_twice(tmp_path):
    db_file = tmp_path / "s.sqlite"
    assert run_script(db_file, "Alpha", "Beta", "Gamma").returncode == 0
    second = run_script(db_file, "Delta", "Echo", "Foxtrot")
    assert second.returncode != 0
    assert "already exist" in second.stderr
