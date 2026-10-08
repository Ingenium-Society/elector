# School Election: Local Network Voting System

A small offline voting system for the school council election. One laptop runs the
server, about 120 voters use their own phones or laptops over a local Wi-Fi network
(no internet), and each voter uses a single-use paper token.

- Full design: [docs/SPEC.md](docs/SPEC.md)
- Build order: [docs/ROADMAP.md](docs/ROADMAP.md)
- How we work together: [CONTRIBUTING.md](CONTRIBUTING.md)

## Status

Skeleton only: folders and empty files. No code has been written yet.
Start with Stage 1 in the roadmap.

## Planned layout

```
app/
  main.py          web server (routes)
  db.py            database helpers
  schema.sql       database tables
  config.py        settings
  static/          voter page (plain HTML/JS, no CDN links)
scripts/           token generator, result export, load test
tests/             automated tests
docs/              spec and roadmap
data/              database and token files (git-ignored, never committed)
```

## Setup (once there is code to run)

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt  # needs internet: do this BEFORE election day
pytest
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Golden rules

1. **Never commit election data.** No database files, token lists, or exports.
   `.gitignore` blocks them. Do not override it.
2. **Anonymity:** the `votes` table never gets a timestamp, token, IP, or device info.
3. **The server decides everything.** Never rely on the browser (JavaScript) to
   enforce a rule; always check again on the server.
4. **No internet at the event.** No CDN links, no downloads. Everything is served
   from the laptop.
