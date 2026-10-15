"""Stage 6 tests for scripts/export_results.py (the official results report).

The script is run the same way a person would run it (as a separate Python
process), pointed at a temporary database with VOTING_DB. The reconciliation
helpers are also tested directly.
"""
import csv
import hashlib
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app import config, db, tokens

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "export_results.py"
OFFLINE = SCRIPT.parent.parent

spec = importlib.util.spec_from_file_location("export_results", SCRIPT)
export_results = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export_results)

RAW_TOKENS = [f"TEST{i:04d}" for i in range(10)]


@pytest.fixture
def election(tmp_path, monkeypatch):
    """A finished election: 3 candidates, 10 tokens, 8 votes (4 / 3 / 1), state RESULTS."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "election.sqlite")
    db.init_db()
    ids = [db.add_candidate(name) for name in ("Aisyah Putri", "Rizky Pratama", "Nadia Kusuma")]
    db.add_token_hashes([tokens.hash_token(t) for t in RAW_TOKENS])
    choices = [ids[0], ids[0], ids[0], ids[0], ids[1], ids[1], ids[1], ids[2]]
    assert db.transition_state("IDLE", "OPEN")
    for raw, candidate in zip(RAW_TOKENS, choices):
        assert db.cast_vote(tokens.hash_token(raw), candidate) == db.VOTE_OK
    assert db.transition_state("OPEN", "CLOSED")
    assert db.transition_state("CLOSED", "RESULTS")
    return tmp_path


def run_export(election, *extra):
    env = dict(os.environ, VOTING_DB=str(election / "election.sqlite"))
    out = election / "out"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--out", str(out), *extra],
        capture_output=True, text=True, env=env, cwd=OFFLINE,
    )
    return result, out


def docx_text(path):
    from docx import Document
    document = Document(path)
    parts = [p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            parts.extend(cell.text for cell in row.cells)
    return "\n".join(parts)


# ---- the export only runs after "Reveal results" ----------------------------

@pytest.mark.parametrize("state", ["IDLE", "OPEN", "CLOSED"])
def test_export_is_refused_before_results_are_revealed(election, state):
    with db.connect() as conn:
        conn.execute("UPDATE config SET value = ? WHERE key = 'state'", (state,))
    result, out = run_export(election)
    assert result.returncode != 0
    assert "Reveal results" in result.stderr
    assert not out.exists()  # nothing leaked


def test_export_creates_all_five_files(election):
    result, out = run_export(election, "--roll-ticks", "8")
    assert result.returncode == 0, result.stderr
    assert sorted(p.name for p in out.iterdir()) == sorted(export_results.ALL_OUTPUTS)


def test_export_will_not_overwrite_an_earlier_export(election):
    first, out = run_export(election)
    assert first.returncode == 0
    before = (out / "results.csv").read_bytes()
    second, _ = run_export(election)
    assert second.returncode != 0
    assert "already contains" in second.stderr
    assert (out / "results.csv").read_bytes() == before


# ---- contents ---------------------------------------------------------------

def test_csv_has_candidate_names_and_totals_only(election):
    _, out = run_export(election)
    with open(out / "results.csv", newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows == [["Candidate", "Votes"], ["Aisyah Putri", "4"], ["Rizky Pratama", "3"], ["Nadia Kusuma", "1"]]


def test_xlsx_matches_the_csv(election):
    from openpyxl import load_workbook
    _, out = run_export(election)
    rows = list(load_workbook(out / "results.xlsx").active.values)
    assert rows == [("Candidate", "Votes"), ("Aisyah Putri", 4), ("Rizky Pratama", 3), ("Nadia Kusuma", 1)]


def test_hash_file_matches_the_database_copy(election):
    _, out = run_export(election)
    digest = hashlib.sha256((out / "election.sqlite").read_bytes()).hexdigest()
    assert (out / "election.sqlite.sha256").read_text().split() == [digest, "election.sqlite"]


def test_report_shows_totals_winner_and_the_same_hash(election):
    _, out = run_export(election, "--roll-ticks", "8")
    text = docx_text(out / "results_report.docx")
    digest = (out / "election.sqlite.sha256").read_text().split()[0]
    assert "Official Election Results" in text
    assert "Aisyah Putri received the most votes: 4 of 8 (50.0%)" in text
    assert digest in text
    assert text.count("PASS") == 4 and "FAIL" not in text


def test_report_contains_the_logo(election):
    _, out = run_export(election)
    from docx import Document
    assert len(Document(out / "results_report.docx").inline_shapes) == 1


# ---- anonymity (AGENTS.md rule 8, SPEC A10) --------------------------------

def test_no_token_or_token_hash_appears_in_any_report_or_sheet(election):
    from openpyxl import load_workbook
    _, out = run_export(election, "--roll-ticks", "8")
    secrets_to_find = RAW_TOKENS + [tokens.hash_token(t) for t in RAW_TOKENS]
    readable = "\n".join([
        (out / "results.csv").read_text(),
        docx_text(out / "results_report.docx"),
        "\n".join(str(v) for row in load_workbook(out / "results.xlsx").active.values for v in row),
    ])
    for secret in secrets_to_find:
        assert secret not in readable


def test_export_script_never_joins_tokens_with_votes():
    # A simple guard on the source: no SQL in the script mentions both tables in one query.
    source = SCRIPT.read_text()
    for chunk in source.split('"""'):
        lowered = chunk.lower()
        if "select" in lowered and "from tokens" in lowered:
            assert "votes" not in lowered.split("from tokens")[1].split(")")[0]


# ---- reconciliation ----------------------------------------------------------

def test_reconciliation_passes_on_a_clean_election(election):
    checks = export_results.reconcile(export_results.collect(), roll_ticks=8)
    assert [status for _, _, status in checks] == ["PASS"] * 4


def test_reconciliation_asks_for_roll_ticks_when_not_given(election):
    checks = export_results.reconcile(export_results.collect())
    assert checks[-1][2] == export_results.TODO


def test_roll_ticks_above_tokens_issued_fail(election):
    checks = export_results.reconcile(export_results.collect(), roll_ticks=11)
    assert checks[-1][2] == export_results.FAIL


def test_mismatch_between_tokens_used_and_ballots_fails_and_is_reported(election):
    # Simulate tampering: a token marked used although no ballot exists for it.
    with db.connect() as conn:
        conn.execute("UPDATE tokens SET used = 1 WHERE used = 0 AND rowid = (SELECT MIN(rowid) FROM tokens WHERE used = 0)")
    result, out = run_export(election)
    assert result.returncode == 2
    assert "RECONCILIATION FAILED" in result.stdout
    assert "RECONCILIATION FAILED" in docx_text(out / "results_report.docx")


# ---- ties and empty elections ------------------------------------------------

def test_a_tie_is_announced_not_hidden(election):
    # Real database: move one of the leader's 4 votes to the runner-up, so it is 3 / 4 / 1,
    # then one more from the leader's side so the top two are level at 3 / 3 / 2.
    with db.connect() as conn:
        conn.execute("UPDATE votes SET candidate_id = 3 WHERE id = (SELECT id FROM votes WHERE candidate_id = 1 LIMIT 1)")
    totals = {c["name"]: c["votes"] for c in export_results.collect()["candidates"]}
    assert totals == {"Aisyah Putri": 3, "Rizky Pratama": 3, "Nadia Kusuma": 2}

    result, out = run_export(election)
    assert result.returncode == 0, result.stderr
    text = docx_text(out / "results_report.docx")
    assert "TIE: Aisyah Putri and Rizky Pratama each received 3 votes" in text
    assert "received the most votes" not in text


def test_no_votes_means_no_leader():
    assert export_results.leaders([{"id": 1, "name": "A", "votes": 0}]) == []
    assert export_results.percent(0, 0) == "0.0%"
