# School Election: Local Network Voting System

A small offline voting system for the school council election. One laptop runs the
server, about 120 voters use their own phones or laptops over a local Wi-Fi network
(no internet), and each voter uses a single-use paper token.

- Full design: [docs/SPEC.md](docs/SPEC.md)
- Build order: [docs/ROADMAP.md](docs/ROADMAP.md)
- How we work together: [CONTRIBUTING.md](CONTRIBUTING.md)
- Notes for AI assistants working here: [AGENTS.md](AGENTS.md)

## Two versions, one repo

| Folder | What it is | Status |
|---|---|---|
| [`offline/`](offline/) | **The real election.** FastAPI + SQLite on one laptop, local Wi-Fi, no internet | Stage 1 in progress |
| [`online/`](online/README.md) | Experimental hosted demo (for example Supabase). **Fake data only** | Not started |

Both live on `main` as separate folders (not as long-lived branches), so a fix to the
shared docs never has to be copied between branches.

## Status

Stage 1 (database schema, config, `GET /api/state`) is in progress in `offline/`.
Everything after Stage 1 is not started. See [docs/ROADMAP.md](docs/ROADMAP.md).

## Layout

```
docs/                shared spec and roadmap
offline/             the real election
  app/
    main.py          web server (routes)
    db.py            database helpers
    schema.sql       database tables
    config.py        settings
    static/          voter page (plain HTML/JS, no CDN links)
  scripts/           token generator, result export, load test
  tests/             automated tests
  data/              database and token files (git-ignored, never committed)
  requirements.txt
  pytest.ini
online/              experimental hosted demo (placeholder, no code yet)
```

## Setup (offline version)

Requires Python 3.10+. Run everything from the `offline/` folder.

```bash
cd offline
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt  # needs internet: do this BEFORE election day
pytest
uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log
```

## Golden rules

1. **Never commit election data.** No database files, token lists, or exports.
   `.gitignore` blocks them. Do not override it.
2. **Anonymity:** the `votes` table never gets a timestamp, token, IP, or device info.
3. **The server decides everything.** Never rely on the browser (JavaScript) to
   enforce a rule; always check again on the server.
4. **No internet at the event.** No CDN links, no downloads. Everything is served
   from the laptop. (This is about `offline/`, the version used on election day.)
5. **Never commit secrets.** Keys for the online demo go in a `.env` file, which is git-ignored.
