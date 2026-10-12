"""Add the candidates to the election database.

Run this once, from the offline/ folder, before the election:

    python scripts/add_candidates.py "Name One" "Name Two" "Name Three"

The names are typed on the command line on purpose: real names are election
data and must not be saved in the repository.
"""
import sys
from pathlib import Path

# Let Python find the "app" package, which lives one folder above scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db  # noqa: E402

EXPECTED = 3  # the design says there are exactly 3 candidates


def main(names):
    names = [name.strip() for name in names if name.strip()]
    if len(names) != EXPECTED:
        sys.exit(f"Please give exactly {EXPECTED} candidate names (got {len(names)}).")
    if len(set(n.lower() for n in names)) != len(names):
        sys.exit("Two candidates have the same name. Nothing was added.")

    db.init_db()
    if db.list_candidates():
        # Never add twice: a second run would give voters 6 buttons.
        sys.exit("Candidates already exist. Nothing was added.")

    for name in names:
        db.add_candidate(name)
    print("Added:", ", ".join(c["name"] for c in db.list_candidates()))


if __name__ == "__main__":
    main(sys.argv[1:])
