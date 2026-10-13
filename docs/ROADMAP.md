# Roadmap

Each stage should run and pass its tests before the next one starts.
Stages 0 to 8 below describe `offline/`, the version used for the real election.
The online track at the bottom is optional and separate.
Suggested: one branch and one pull request per stage.

| Stage | Goal | Done when |
|---|---|---|
| 0 | Repo skeleton (created by the setup script) | Folders, docs and git remote exist |
| 1 | Database schema, config, and `GET /api/state` with smoke tests | `pytest` passes; page shows the state |
| 2 | Candidates: add the 3 candidates to the DB | `GET /api/candidates` returns 3 names |
| 3 | Tokens and voting: `generate_tokens.py`, `POST /api/token/check`, `POST /api/vote` with the atomic transaction | Double-vote test passes; vote only accepted when state is OPEN |
| 4 | Admin Open/Close/Reveal, localhost-only password-protected admin panel, WebSocket state/turnout pushes, candidate selection + confirmation | Admin transitions are guarded; connected voter pages update; admin can reveal totals |
| 5 | Voter UI polish: accessibility, clear errors, reconnect behavior, and real-phone/browser compatibility checks | Works on old and new phones, offline |
| 6 | Results and audit: reconciliation, `export_results.py`, SHA-256 of DB | Counts reconcile; XLSX produced |
| 7 | Hardening: load test (120 clients), anonymity audit (DB, logs, exports), rate limiting | All tests in SPEC section 12 pass |
| 8 | Dry runs: 30+ real phones, then full rehearsal with the Class Representative Council | Sign-off |

**Stage 4 implementation:** branch `stage-4-admin-controls` (PR pending). Code is not merged or production-approved until tests and review pass.

**Review rule:** anything touching the vote transaction, the votes table, logging,
or exports needs a second person (or a teacher/IT staff) to review it before merging.

## Online track (`online/`, optional, not started)

An experimental hosted demo with fake data only. It is **not** the election system.
Do not start it before offline Stage 3 (tokens and voting) is done. These stages are a
proposal and can change. See [online/README.md](../online/README.md) for how it differs.

| Stage | Goal | Done when |
|---|---|---|
| O0 | Decide whether an online demo is wanted, and agree the fake-data rule | Decision written in `online/README.md` |
| O1 | Hosted Postgres schema, one `cast_vote` database function, Row Level Security | Double-vote test passes against the database |
| O2 | Realtime state: Open/Close reaches all voter pages | Pressing Open switches connected pages |
| O3 | Voter page for the online version (reuse the offline page design) | Works on phones |
| O4 | Deploy the demo with dummy tokens and candidates | Demo link works; anonymity limits are listed |
