import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Where the election database lives. By default it is offline/data/election.sqlite
# (git-ignored). Set the environment variable VOTING_DB to use another file,
# for example a copy for a dry run.
DB_PATH = Path(os.environ.get("VOTING_DB", BASE_DIR / "data" / "election.sqlite"))

# The admin password. It is read from the ADMIN_PASSWORD environment variable and
# is never written in the code or committed. If it is not set, the admin routes
# are switched off completely (they answer 503), which is the safe default.
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

# The election can only move in one direction: IDLE -> OPEN -> CLOSED -> RESULTS.
STATES = ("IDLE", "OPEN", "CLOSED", "RESULTS")
