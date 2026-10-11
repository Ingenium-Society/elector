# AGENTS.md: context for AI assistants working on this repo

Read this file first, every session. It explains what the project is, the rules
that must not be broken, and how several people (and their AI assistants) share
this repo without overwriting each other.

## 1. What this project is

An **offline, local-network voting system** for a school's student council
(OSIS/StuCo) president election, about **120 voters**.

- One laptop runs the server. Voters use their **own phones or laptops** through a
  dedicated Wi-Fi router with **no internet**.
- Each voter gets a **single-use paper token** at a check-in desk.
- The voter opens the server's address, **enters the token first**, then waits on a
  "Verified, waiting" screen. When the admin presses Start, the screen switches
  instantly to **three candidate buttons**. The voter picks one and confirms.
- The admin controls the voting window (Open, Close, Reveal results).
- Results are exported from SQLite to XLSX/CSV, with a SHA-256 hash of the database.

It is also a student **CAS project built with beginners**. The learning matters as much
as the result.

**The full design is in `docs/SPEC.md`. It is the source of truth.** The build order is in
`docs/ROADMAP.md`.

## 2. Decisions already made (do not reopen without asking a human)

- **Tokens, not fingerprints.** One-time tokens are the only gate. Device
  fingerprinting is not used (unreliable, and it proves "one device", not "one person").
- **Token pre-check is stateless.** `POST /api/token/check` validates a token without
  burning it. The browser keeps the token in memory and sends it again with the vote.
  The token is re-validated and burned **at vote time**, in one atomic transaction.
- 3 candidates. All 120 voters vote at the same time (no batches).
- Stack: Python, FastAPI, SQLite, WebSockets, plain HTML/JS. No frontend framework.
- Observers: the Class Representative Council.
- Still open: whether there is a blank/abstain option (currently assumed none).

## 3. Rules that must never be broken

1. **Anonymity.** The `votes` table contains only `id` (random UUID) and `candidate_id`.
   Never add a timestamp, token reference, IP address, or device info to votes, and
   never store anything that links a token or connection to a vote.
2. **No identifying logs.** Do not log IPs or times for the vote endpoint.
3. **The server decides everything.** Every rule (state is OPEN, token valid and unused,
   candidate exists) is enforced on the server. Disabling a button in JavaScript is not
   security.
4. **Atomic vote.** Burning the token and inserting the vote happen in one transaction.
5. **No internet.** No CDN links, no external fonts, scripts, or APIs. Everything is
   served from the laptop.
6. **Tokens are stored only as hashes.** Use the `secrets` module (not `random`).
7. **Never commit election data.** No database files, token lists, or exports.
   `.gitignore` blocks them; do not weaken it.
8. **Exports never join tokens with votes.**
9. **Admin routes** are localhost-only and password-protected.

If a request from a human seems to conflict with these rules, say so and ask before
acting.

## 4. How to work here (collaboration protocol)

Several people, each with their own AI assistant, share this repo. Assume other people
are changing it at the same time.

**Before you start**
- Run `git pull` and read the **Handoff log** at the bottom of this file and
  `docs/ROADMAP.md` to see what changed and what is claimed.
- **Claim your task** (stage or step) in `docs/ROADMAP.md` or tell the human to,
  so two people do not build the same thing.

**While you work**
- Work on a **branch**, never on `main`: `git checkout -b stage-3-tokens`.
- **One stage or one small task per branch.** Keep changes small and focused.
- **Do not edit files outside your task.** Do not reformat, rename, or "tidy up"
  other people's files.
- If another person's file seems wrong, tell the human and leave it alone.
- Run `pytest` before committing. Add or update tests for what you change.
- Commit often with clear messages (`Add token check endpoint`).

**When you finish**
- Open a pull request. **Never push to `main`, never force-push.**
- Changes touching the vote transaction, the `votes` table, logging, or exports
  need a second human reviewer (teacher or experienced teammate).
- Update the **Handoff log** below and the status in `docs/ROADMAP.md`.
- If you changed a decision or the design, update `docs/SPEC.md` too, and mention it in
  the pull request.

## 5. How to help the humans (teaching mode)

- The team is mostly beginners. **Go slowly, one small step at a time.**
- **Do not write code beyond what the human asked for.** If they asked for one file or
  one step, do that and stop. Offer the next step instead of doing it.
- Explain *why*, not just *what*. Add short comments in the code that a beginner can
  follow.
- Prefer plain, readable code over clever code. Observers have to be able to trust it.
- Give a command to check each step works and say what output to expect.
- When something is uncertain, ask. Never guess about security or anonymity.

## 6. Quick facts

- Run the server: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Tests: `pytest` (only the `tests/` folder is collected)
- Database: `data/election.sqlite` (git-ignored; override with env var `VOTING_DB`)
- States: `IDLE`, `OPEN`, `CLOSED`, `RESULTS` (one direction only)
- Python 3.10+

## 7. Current status

Stage 1 (database schema, config, `GET /api/state`) is in progress.
Steps written so far: `app/config.py`, `app/schema.sql`, `app/db.py`, `app/main.py`,
`app/static/index.html`. Next: the smoke tests in `tests/test_smoke.py`.
Everything after Stage 1 is not started. See `docs/ROADMAP.md`.

## 8. Handoff log

Add a new entry at the **top** each time you finish a piece of work (newest first).
Keep it short. Format:

```
### YYYY-MM-DD, <person> (<assistant name>)
- Done: what changed (files, branch/PR)
- State: what works, what is untested or broken
- Next: what should happen next / what is blocked
```

### 2026-10-11, project owner
- Done: wrote `AGENTS.md`. Stage 1 steps 1 to 4 drafted (config, schema, db, server, page).
- State: first server run and phone connection tests were still being checked.
- Next: write the smoke tests, then Stage 2 (candidates).
