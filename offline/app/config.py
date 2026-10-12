import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Where the election database lives. By default it is offline/data/election.sqlite
# (git-ignored). Set the environment variable VOTING_DB to use another file,
# for example a copy for a dry run.
DB_PATH = Path(os.environ.get("VOTING_DB", BASE_DIR / "data" / "election.sqlite"))

# The election can only move in one direction: IDLE -> OPEN -> CLOSED -> RESULTS.
STATES = ("IDLE", "OPEN", "CLOSED", "RESULTS")
