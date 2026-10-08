# Roadmap

Each stage should run and pass its tests before the next one starts.
Suggested: one branch and one pull request per stage.

| Stage | Goal | Done when |
|---|---|---|
| 0 | Repo skeleton (created by the setup script) | Folders, docs and git remote exist |
| 1 | Database schema, config, and `GET /api/state` with smoke tests | `pytest` passes; page shows the state |
| 2 | Candidates: add the 3 candidates to the DB | `GET /api/candidates` returns 3 names |
| 3 | Tokens and voting: `generate_tokens.py`, `POST /api/token/check`, `POST /api/vote` with the atomic transaction | Double-vote test passes; vote only accepted when state is OPEN |
| 4 | State control: admin Open/Close/Reveal (localhost + password), WebSocket pushing state to voters, candidate buttons + confirm step | Pressing Open switches all connected pages instantly |
| 5 | Voter UI polish: token entry, "Verified, waiting" screen, errors, reconnect banner | Works on old and new phones, offline |
| 6 | Results and audit: reconciliation, `export_results.py`, SHA-256 of DB | Counts reconcile; XLSX produced |
| 7 | Hardening: load test (120 clients), anonymity audit (DB, logs, exports), rate limiting | All tests in SPEC section 12 pass |
| 8 | Dry runs: 30+ real phones, then full rehearsal with the Class Representative Council | Sign-off |

**Review rule:** anything touching the vote transaction, the votes table, logging,
or exports needs a second person (or a teacher/IT staff) to review it before merging.
