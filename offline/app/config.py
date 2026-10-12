import os
from pathlib import Path

# The offline/ folder (two levels up from this file: app/config.py -> app -> offline)
BASE_DIR = Path(__file__).resolve().parent.parent

# Where the database file lives (git-ignored, never committed).
# If the VOTING_DB environment variable is set, use that path instead.
# Tests use this so they never touch the real election database.
DB_PATH = Path(os.environ.get("VOTING_DB", BASE_DIR / "data" / "election.sqlite"))

# The only valid election states, in order. See docs/SPEC.md section 5.
STATES = ("IDLE", "OPEN", "CLOSED", "RESULTS")
