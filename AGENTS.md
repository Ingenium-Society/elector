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

### Repo layout: two versions

```
docs/      shared spec and roadmap
offline/   the real election: FastAPI + SQLite, local Wi-Fi, no internet
online/    experimental hosted demo (not started; fake data only)
```

Anything in this file about running, testing or editing code means `offline/` unless it says
otherwise. Work on `online/` only if a human asks for it. Never put real election data in
`online/`. See `online/README.md` for how it differs.

## 2. Decisions already made (do not reopen without asking a human)

- **Tokens, not fingerprints.** One-time tokens are the only gate. Device
  fingerprinting is not used (unreliable, and it proves "one device", not "one person").
- **Token pre-check is stateless.** `POST /api/token/check` validates a token without
  burning it. The browser keeps the token in memory and sends it again with the vote.
  The token is re-validated and burned **at vote time**, in one atomic transaction.
- 3 candidates. All 120 voters vote at the same time (no batches).
- Stack: Python, FastAPI, SQLite, WebSockets, plain HTML/JS. No frontend framework.
- Observers: the Class Representative Council.
- **Two versions in one repo:** `offline/` (the real election) and `online/` (an experimental
  demo). They are two folders on `main`, not two long-lived branches. Tag the exact commit
  used on election day (for example `election-v1`).
- **No blank/abstain option.** Decided by the project owner on 2026-10-13: voters choose
  one of the 3 candidates.
- `GET /api/candidates` answers only while the state is `OPEN` (403 otherwise).

## 3. Rules that must never be broken

These rules are written for `offline/`, the real election. Rules 1 to 4 and 6 to 8 also
apply to `online/` as far as the platform allows. Rules 5 and 9 are specific to the offline
setup. Where `online/` cannot meet a rule, it must say so in `online/README.md`.

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
- **One folder per pull request.** Change `offline/` or `online/`, not both. If both need the
  same change, make two pull requests.
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

- Run these from the `offline/` folder: `cd offline`
- Run the server: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log`
  (`--no-access-log` is required: uvicorn's default log writes each voter's IP next to
  `POST /api/vote`, which breaks rule 2.)
- Tests: `pytest` (only `offline/tests/` is collected)
- Database: `offline/data/election.sqlite` (git-ignored; override with env var `VOTING_DB`)
- States: `IDLE`, `OPEN`, `CLOSED`, `RESULTS` (one direction only)
- Python 3.10+

## 7. Current status

Stages 1 and 2 are done and merged (schema, config, `GET /api/state`, candidates).
Stage 3 (tokens and voting) is built on branch `stage-3-tokens`, waiting for a second human
reviewer: `scripts/generate_tokens.py`, `POST /api/token/check`, `POST /api/vote`.
Everything after Stage 3 is not started. See `docs/ROADMAP.md`.

Repo restructured on 2026-10-11: the code now lives in `offline/`, and `online/` is a
placeholder with no code (branch `restructure-offline-online`).

## 8. Handoff log

Add a new entry at the **top** each time you finish a piece of work (newest first).
Keep it short. Format:

```
### YYYY-MM-DD, <person> (<assistant name>)
- Done: what changed (files, branch/PR)
- State: what works, what is untested or broken
- Next: what should happen next / what is blocked
```

### 2026-10-13, project owner (Claude), branch `stage-3-tokens`
- Done (3 commits, one per step, 74 tests passing):
  1. `app/tokens.py` (8-character tokens from the 31-letter alphabet, `secrets`, normalize,
     SHA-256) and `scripts/generate_tokens.py N` (stores only hashes; writes readable tokens to
     git-ignored `offline/data/tokens.txt`; refuses to run twice or overwrite the file; does not
     print the tokens).
  2. `POST /api/token/check`: `{token}` -> `{valid: bool}`; IDLE or OPEN only (403 otherwise);
     burns nothing, stores nothing; unknown and used tokens look the same.
  3. `POST /api/vote`: `{token, candidate_id}`; 403 unless OPEN; 400 for unknown candidate,
     bad or used token (same message). `db.cast_vote()` runs `BEGIN IMMEDIATE`, re-checks OPEN
     inside the transaction, burns the token (`used = 0` guard), inserts `(uuid4, candidate_id)`,
     commits. Any failure rolls back, so a rejected vote never burns a token.
- State: tested with 20 simultaneous threads on one token (exactly 1 vote), double vote,
  every wrong state, unknown candidate, forced rollback, and checks that nothing in `votes`
  mentions the token. Also run once against a real uvicorn server (check, vote, double vote).
- NEEDS A SECOND HUMAN REVIEWER before merging: it adds the vote transaction and writes to
  the `votes` table (see section 4). Please read `db.cast_vote()` and `tests/test_vote.py`.
- Found: uvicorn's default access log prints voter IPs next to `/api/vote` (rule 2). The run
  command now has `--no-access-log` (README and section 6). Anyone starting the server another
  way must keep that flag. Nothing in the app code logs.
- Not done on purpose (later stages): rate limiting on check/vote (Stage 7), admin
  Open/Close/Reveal (Stage 4; until then state can only be changed in the database), WebSocket
  push, voter UI for token entry and candidate buttons (Stages 4 and 5), results export (Stage 6).
- Known limit: SHA-256 of a 40-bit token is unsalted. With ~130 tokens and rate limiting this
  matches the spec, but the reviewer should confirm it is acceptable.
- Next: review and merge `stage-3-tokens`; then Stage 4 (admin state control + WebSocket).

### 2026-10-13, project owner (Claude), branch `stage-2-candidates`
- Done: `db.add_candidate()` and `db.list_candidates()`; `GET /api/candidates` returns
  `{"candidates": [{"id", "name"}, ...]}` in id order; `offline/scripts/add_candidates.py` adds
  exactly 3 names given on the command line (refuses wrong count, duplicates, or a second run).
  Names are typed at the command line so real names never enter the repo. 7 new tests in
  `offline/tests/test_candidates.py`.
- State: `pytest` passes from `offline/` (20 passed). This branch builds on
  `stage-1-config-match-spec`, which builds on `stage-1-smoke-tests`: merge in that order.
- Not done on purpose: the spec says `/api/candidates` is for voters "when OPEN". It currently
  answers in every state. Locking it to OPEN needs the state rules from Stage 3/4, so a human
  should decide whether to restrict it now. Also still open: a blank/abstain option.
- Next: Stage 3 (tokens and voting). That touches the vote transaction and `votes` table,
  so it needs a second human reviewer.

### 2026-10-13, project owner (Claude), branch `stage-2-candidates` (update)
- Done: on the owner's instruction, `GET /api/candidates` now returns 403 unless the state is
  `OPEN` (matches SPEC section 7). Decided: no blank/abstain option. Updated `docs/SPEC.md`
  section 15. Tests set the state first and check IDLE/CLOSED/RESULTS are refused.
- State: `pytest` passes from `offline/` (23 passed).
- Next: Stage 3 (tokens and voting). Needs a second human reviewer. The branch
  `fix-config-match-spec` (same config change, no tests) was not merged; the owner can delete it.

### 2026-10-12, project owner (Claude), branch `stage-1-config-match-spec`
- Done: `offline/app/config.py` now matches the spec: database `data/election.sqlite`,
  overridable with env var `VOTING_DB`, and `STATES = IDLE, OPEN, CLOSED, RESULTS` (the old
  `STATUS` list with `IN_PROGRES` was removed; nothing used it). Added 3 tests for this.
  This branch builds on `stage-1-smoke-tests`: merge that one first.
- State: `pytest` passes from `offline/` (13 passed).
- Next: Stage 2 (candidates).

### 2026-10-12, project owner (Claude)
- Done: wrote `offline/tests/test_smoke.py` (10 tests) on branch `stage-1-smoke-tests`. They
  cover table creation, state starting as IDLE and surviving a restart, `GET /api/state`,
  the voter page, and three guards: `votes` has only `id` and `candidate_id`, `tokens` has only
  `token_hash` and `used`, and the page has no internet links. Tests use a temporary database
  (they patch `config.DB_PATH`), so they never touch `offline/data/`.
- State: `pytest` passes from `offline/` (10 passed). No app code was changed.
- Next: owner decides whether to match `config.py` to the spec (`election.sqlite`, `VOTING_DB`,
  states IDLE/OPEN/CLOSED/RESULTS, not `IN_PROGRES`). After that, Stage 2 (candidates).
  The anonymity guard tests touch the `votes` table, so the pull request needs a second reviewer.

### 2026-10-11, project owner (Claude)
- Done: moved `app/`, `scripts/`, `tests/`, `data/`, `pytest.ini`, `requirements.txt` into
  `offline/`; added `online/README.md` (placeholder, no code); fixed `.gitignore` for the
  nested `data/` folder and added `.env`; updated README, CONTRIBUTING, ROADMAP (added an
  online track), SPEC (scope note, v0.4) and this file. Branch `restructure-offline-online`.
- State: server starts from `offline/` and `/api/state` works. `tests/test_smoke.py` is still
  empty, so `pytest` collects nothing yet. Not changed on purpose: `offline/app/config.py`
  uses `data/db.sqlite3` and a `STATUS` list containing `IN_PROGRES`, which differs from this
  file and the spec (`election.sqlite`, states IDLE/OPEN/CLOSED/RESULTS, `VOTING_DB`).
- Next: owner decides whether to match `config.py` to the spec; then the smoke tests.
  Anyone with an open branch must rebase onto this one, because file paths changed.

### 2026-10-11, project owner
- Done: wrote `AGENTS.md`. Stage 1 steps 1 to 4 drafted (config, schema, db, server, page).
- State: first server run and phone connection tests were still being checked.
- Next: write the smoke tests, then Stage 2 (candidates).
