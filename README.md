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
```

### Run the server

```bash
ADMIN_PASSWORD='a-long-password-only-the-admin-knows' \
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log --log-level warning
```

On Windows (PowerShell): `$env:ADMIN_PASSWORD='...'` first, then the `uvicorn` line on one line.

- **Both log flags are required.** Without them uvicorn prints each voter's address
  (next to `POST /api/vote` and next to every `WebSocket /ws` connection), which breaks the
  anonymity rule. `--no-access-log` alone is not enough for the WebSocket lines.
- **Run ONE server process.** Never add `--workers`: the list of connected voter pages lives
  in that one process's memory.
- **No `ADMIN_PASSWORD`, no admin.** The admin routes answer 503 until it is set.

### Open, close and reveal (from the server laptop only)

Voters' phones are refused (403), even with the right password. The password goes in a
header, never in the web address.

```bash
curl -X POST -H "X-Admin-Password: $ADMIN_PASSWORD" http://127.0.0.1:8000/admin/open
curl        -H "X-Admin-Password: $ADMIN_PASSWORD" http://127.0.0.1:8000/admin/status
curl -X POST -H "X-Admin-Password: $ADMIN_PASSWORD" http://127.0.0.1:8000/admin/close
curl -X POST -H "X-Admin-Password: $ADMIN_PASSWORD" http://127.0.0.1:8000/admin/reveal
```

The steps only go forward: IDLE, OPEN, CLOSED, RESULTS. A step out of order answers 409
and changes nothing. There is no way back, so check candidates and tokens before Open.
Every voter page that is connected to `/ws` hears each change at the same moment.

## Golden rules

1. **Never commit election data.** No database files, token lists, or exports.
   `.gitignore` blocks them. Do not override it.
2. **Anonymity:** the `votes` table never gets a timestamp, token, IP, or device info.
3. **The server decides everything.** Never rely on the browser (JavaScript) to
   enforce a rule; always check again on the server.
4. **No internet at the event.** No CDN links, no downloads. Everything is served
   from the laptop. (This is about `offline/`, the version used on election day.)
5. **Never commit secrets.** Keys for the online demo go in a `.env` file, which is git-ignored.
