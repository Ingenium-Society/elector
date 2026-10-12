"""Make the single-use voting tokens.

Run this once, from the offline/ folder, before the election:

    python scripts/generate_tokens.py 130

130 = eligible voters plus a few spares. The script:
  * saves only the HASH of each token in the database, and
  * writes the readable tokens to a text file so you can print them on slips.

The text file is election data. It is git-ignored: never commit it, and
delete it after the slips are printed.
"""
import argparse
import sys
from pathlib import Path

# Let Python find the "app" package, which lives one folder above scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, db, tokens  # noqa: E402

DEFAULT_OUT = config.BASE_DIR / "data" / "tokens.txt"


def main():
    parser = argparse.ArgumentParser(description="Generate single-use voting tokens.")
    parser.add_argument("count", type=int, help="how many tokens to make")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="where to write the readable tokens (default: data/tokens.txt)")
    args = parser.parse_args()

    if not 1 <= args.count <= 1000:
        sys.exit("Please ask for between 1 and 1000 tokens.")
    if args.out.exists():
        sys.exit(f"{args.out} already exists. Move or delete it first. Nothing was made.")

    db.init_db()
    if db.count_tokens() > 0:
        # Making more would mix old and new slips and break the count.
        sys.exit("Tokens already exist in the database. Nothing was made.")

    # A set cannot hold the same token twice, so every token is different.
    made = set()
    while len(made) < args.count:
        made.add(tokens.generate_token())
    readable = sorted(made)

    db.add_token_hashes([tokens.hash_token(t) for t in readable])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(readable) + "\n")

    # Do not print the tokens themselves: terminal history can be read later.
    print(f"Made {args.count} tokens.")
    print(f"Readable tokens written to: {args.out}")
    print("Only their hashes are stored in the database.")


if __name__ == "__main__":
    main()
