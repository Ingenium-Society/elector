# OSIS/StuCo Election: Local Network Voting System
**Specification v0.4 (draft): scope note for the offline/online split**

> **Scope:** this spec describes the **offline** version (`offline/`), which is the version
> used for the real election. An experimental online demo (`online/`) is not covered here;
> see `online/README.md` for how it differs.

---

## 1. Overview

A local, offline voting system for the school's student council president election. A laptop acts as the server. About 120 voters use their own phones or laptops, connected through a dedicated Wi-Fi router with no internet access. Voters authenticate with single-use paper tokens. The server controls when voting opens and closes.

### Goals
- One eligible student, one vote.
- Voter anonymity: no one, including the admin, can link a vote to a person.
- Voting only possible while the admin has opened it.
- Verifiable results (counts reconcile; data integrity can be checked).
- Simple enough to run reliably on election day.

### Non-goals
- Remote or online voting outside the room. (An experimental online demo lives in `online/`; it is not the election system.)
- Protection against a fully malicious admin who controls the laptop (mitigated by process, see §10).
- Device fingerprinting as the primary anti-fraud mechanism (see §6).

---

## 2. Roles

| Role | Responsibility |
|---|---|
| **Voter** | Takes a token, connects to the server, selects a candidate, confirms. |
| **Check-in staff** (teacher/committee) | Verifies identity against the voter roll, ticks the name, hands out a random token slip. |
| **Admin** | Operates the server laptop: start/close voting, reveal results. |
| **Observers** | The Class Representative Council (plus candidate representatives and a teacher, if the school wants); witness setup, voting, and counting. |

---

## 3. System Architecture

```
 [Voter phones/laptops] --Wi-Fi--> [Dedicated router, offline] --Ethernet--> [Server laptop]
                                                                              |- Web server (HTTP + WebSocket)
                                                                              |- SQLite database
                                                                              |- Admin panel (localhost only)
```

### Suggested stack
| Layer | Choice | Reason |
|---|---|---|
| Backend | Python + FastAPI (or Node + Express) | Simple, readable, easy for observers to review |
| Real-time | WebSockets | Voter screens switch state instantly when admin presses Start/Close |
| Database | SQLite | Zero setup, sufficient for 120 votes |
| Frontend | Single HTML + vanilla JS page | No build step, works on any phone browser |
| Export | Python (`openpyxl` / `pandas`) | SQLite to XLSX/CSV |

### Hardware and network
- **Server laptop:** any 4 to 10 year old laptop; dual-core, 4 GB RAM minimum (8 GB comfortable). Plugged in, battery healthy.
- **Router:** dual-band (2.4/5 GHz), Wi-Fi 5/6; ideally two access points for 120 clients.
- **Connection:** laptop on router via Ethernet; static IP (e.g. `192.168.10.1`).
- **Router config:**
  - DHCP pool of at least 200 addresses
  - Client/AP isolation disabled
  - WPA2/WPA3 with strong password
  - No internet uplink
- **Access:** QR code on the wall encoding `http://192.168.10.1:8000`, plus the URL printed in text.
- **Laptop settings on the day:** disable sleep, screen lock, and automatic updates; allow the server port through the firewall on the private network profile.
- **Backup:** second laptop with identical code, USB stick with a database copy.

---

## 4. Election Flow

1. **Before election day**
   - Admin generates N tokens (N = eligible voters + a small number of spares, e.g. 120 + 10).
   - Tokens are printed on slips, **shuffled**, and folded.
   - Voter roll (paper) prepared.
2. **Check-in desk**
   - Staff verify the student, tick the name on the paper roll, student draws a slip from a box.
   - No record links name to token.
3. **Connecting and token pre-check (before voting opens)**
   - Student joins the election Wi-Fi, scans the QR code or opens the URL.
   - Page asks for the **token first**. The voter types it in and the server checks that it is valid and unused (the token is **not** burned yet).
   - If valid, the page shows **"Verified. Waiting for voting to start"**. If invalid, the voter sees an error and can ask check-in staff for a replacement slip (a spare).
4. **Voting window**
   - Admin presses **Start**. All verified pages switch **instantly** to the three candidate buttons via WebSocket; no typing needed.
   - Voter picks a candidate and confirms. The page sends the token (held in browser memory) together with the choice.
   - Server **re-validates the token at vote time**, records the anonymous vote, and burns the token in one atomic transaction.
   - Voter sees "Your vote has been recorded" (no receipt, no code).
   - Late joiners who connect after Start enter their token and go straight to the candidate buttons.
5. **Close**
   - Admin presses **Close**. All pages show "Voting closed". Further requests are rejected.
6. **Counting**
   - Reconciliation check (see §8), then results revealed to observers and the audience.
7. **After**
   - Export, hash, archive, and delete unnecessary data (see §9).

---

## 5. Server State Machine

```
IDLE --(admin: Open)--> OPEN --(admin: Close)--> CLOSED --(admin: Reveal)--> RESULTS
```

| State | Voter screen | `POST /vote` |
|---|---|---|
| IDLE | Token entry, then "Verified. Waiting for voting to start" | Rejected |
| OPEN | 3 candidate buttons (token already verified), or token entry for late joiners | Accepted if valid |
| CLOSED | "Voting closed" | Rejected |
| RESULTS | Final totals | Rejected |

- State is stored server-side and persisted, so a restart returns to the correct state.
- Transitions are one-directional (no reopening after CLOSED) unless an observer-approved manual override is logged.

---

## 6. Voter Authentication: Tokens (not fingerprints)

**Decision:** one-time tokens are the primary mechanism. Device fingerprinting is *not* used as the gate.

**Why:** fingerprints collide (many students own identical phones, so honest voters get blocked) and are easy to evade (incognito mode, another browser). They also prove "one device", not "one person".

### Token design
- Format: 8 characters from an unambiguous alphabet (e.g. `ABCDEFGHJKMNPQRSTUVWXYZ23456789`), displayed as `K7M2-9QXP`.
- Generated with a cryptographically secure RNG (`secrets` module).
- Stored **only as a hash** (SHA-256) in the database.
- Single use: burned atomically on a successful vote.
- Entry is case-insensitive and ignores hyphens/spaces.

### Secondary signal (optional)
- A browser cookie flag `has_voted=true` set after voting, to show "You have already voted" quickly.
- This is a convenience and a soft signal only. It is **never stored with a vote or a token**.

### Brute-force protection
- Rate limit token attempts per IP (e.g. 5 failures, then 30 s lockout).
- Failures are counted in memory only (no per-voter log persisted).

### Token pre-check design
- **Stateless:** the server does not keep a "session" for verified voters. After a successful check, the browser holds the token in memory (JS variable or `sessionStorage`) and sends it again with the vote. The server therefore re-validates at vote time, which is the only check that counts.
- **Why this is better than server-side sessions:** a server restart or WebSocket drop loses nothing; the page simply reconnects and shows the right screen. It also avoids storing any server-side link between a connection and a token.
- **A passed pre-check is not a reservation.** Two devices could both pass the check with the same token, but only the first `POST /api/vote` succeeds; the second is rejected as already used.
- **Rate limiting applies to the check endpoint too**, since it tells an attacker whether a guess is valid.
- **Page refresh:** if the voter refreshes before voting, they re-enter the token (token stays valid until burned).
- **Optional admin aid:** the admin panel may show a live in-memory count of "verified and waiting" clients to decide when to press Start. This is a number only; no token hashes or identities are stored or displayed.
- **Benefit:** token typos and bad slips are caught during the waiting time, and the load at the moment of Start is just 120 small vote requests.

---

## 7. Data Model (SQLite)

```sql
-- Election configuration
CREATE TABLE config (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL            -- e.g. state = IDLE/OPEN/CLOSED/RESULTS
);

CREATE TABLE candidates (
  id   INTEGER PRIMARY KEY,
  name TEXT NOT NULL
);

-- Which tokens exist and whether burned. No timestamp, no voter reference.
CREATE TABLE tokens (
  token_hash TEXT PRIMARY KEY,
  used       INTEGER NOT NULL DEFAULT 0
);

-- Anonymous ballots. No token reference, no timestamp, random ID.
-- WITHOUT ROWID so insertion order is not preserved as a hidden timeline.
CREATE TABLE votes (
  id           TEXT PRIMARY KEY,       -- random UUID v4
  candidate_id INTEGER NOT NULL REFERENCES candidates(id)
) WITHOUT ROWID;
```

### Vote transaction (atomic)
```sql
BEGIN IMMEDIATE;
  UPDATE tokens SET used = 1 WHERE token_hash = :h AND used = 0;
  -- if rows affected != 1: ROLLBACK and return "invalid or already used"
  INSERT INTO votes (id, candidate_id) VALUES (:uuid, :cid);
COMMIT;
```
The server also verifies `state == OPEN` and that `candidate_id` exists before running the transaction.

---

## 8. API Endpoints

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/` | Voters | Voter page |
| WS | `/ws` | Voters | Pushes state changes (`IDLE/OPEN/CLOSED/RESULTS`) as `{"state": ...}`. The "votes cast" count is not pushed yet (planned) |
| GET | `/api/state` | Voters | Current state (fallback if WebSocket drops) |
| POST | `/api/token/check` | Voters (IDLE or OPEN) | `{token}` returns `{valid: true/false}`. Does **not** burn the token. Rate limited. |
| GET | `/api/candidates` | Voters (when OPEN) | Candidate list |
| POST | `/api/vote` | Voters (when OPEN) | `{token, candidate_id}`. Token is **re-validated and burned here**. |
| POST | `/admin/open` | Admin | IDLE to OPEN |
| POST | `/admin/close` | Admin | OPEN to CLOSED |
| POST | `/admin/reveal` | Admin | CLOSED to RESULTS |
| GET | `/admin/status` | Admin | Votes cast / tokens issued, state |
| POST | `/admin/export` | Admin | Generate results files |

**Admin protection:** admin routes accept requests from `127.0.0.1` / `::1` only **and** require an admin password. Voters on the LAN must not be able to reach them.
- The password comes from the `ADMIN_PASSWORD` environment variable and is sent in the `X-Admin-Password` header, never in the URL. With no password set, admin answers 503.
- Answers: 403 not from the laptop (checked first), 401 wrong password, 409 step out of order (nothing changes, nothing is pushed), 200 `{"state": ...}`.
- `GET /admin/status` returns only `state`, `tokens_issued` and `votes_cast`, never per-candidate numbers.
- The server must run as ONE process: the `/ws` connection list is in memory.

**Server-side validation on every vote:** state is OPEN, token valid and unused, candidate valid. The UI disabling buttons is a convenience, never a security control.

### Voter UI requirements
- Mobile-first, large touch targets, readable without zoom.
- Screen sequence: **token entry, verified/waiting, candidate buttons, confirm, done.**
- Token input auto-uppercases and ignores spaces/hyphens; shows a clear "Verified" state so the voter knows they are ready.
- Three candidate buttons, then a **confirmation step** ("Vote for Candidate B? Confirm / Back").
- After submitting, buttons are disabled and the result message shown; a refresh does not allow re-voting (server rejects it).
- Clear error messages: invalid token, already used, voting not open.
- Connection-lost banner with automatic reconnect.

---

## 9. Anonymity and Privacy Requirements

| # | Requirement |
|---|---|
| A1 | Votes table contains **no** token, IP, device info, or timestamp. |
| A2 | Vote IDs are random UUIDs; table is `WITHOUT ROWID`; exports are shuffled. |
| A3 | Tokens table has `used` flag only (no time of use). |
| A4 | Token slips are shuffled and drawn from a box; no record of name to token. |
| A5 | Web server **access logging disabled** for `/api/vote` (or logs not retained). |
| A6 | No IP address or fingerprint is written to disk alongside any vote/token action. |
| A7 | Live display shows only "votes cast: X / N", never per-candidate counts. |
| A8 | Results are revealed only as totals (no per-batch, per-class breakdown). |
| A9 | No vote receipt or confirmation code shown to the voter. |
| A10 | Export never joins tokens with votes. |
| A11 | After the election, unused tokens are invalidated; data retention follows school policy and personal data is not collected beyond the paper roll. |
| A12 | The token pre-check is stateless: no server-side record links an IP, connection, or session to a token. Check requests are not logged, and any "verified and waiting" count is held in memory only. |

**Known limit:** the person controlling the laptop could, in principle, alter the code to collect more data. This is addressed through process controls (§10), not code alone.

---

## 10. Threat Model

| Threat | Mitigation |
|---|---|
| Double voting | Single-use tokens, atomic transaction, paper voter roll |
| Voting outside the window | Server-side state check |
| Bypassing GUI with manual requests | Server-side validation on every request |
| Token guessing | 40-bit tokens, only ~130 valid, rate limiting |
| Duplicate/extra tokens handed out | Count reconciliation: issued = used + unused |
| Wi-Fi sniffing | Offline network, WPA2/3, password only given on-site |
| Rogue lookalike Wi-Fi | Official SSID printed on QR/poster, staff watch the room |
| Coercion / vote buying | Voting supervised in the room, no receipts |
| Admin tampering with results | Observers present, code reviewed by a teacher, hash of final DB published, paper backup |
| Server crash | Votes written to disk immediately; spare laptop; DB backup on USB |
| Wi-Fi overload | Dedicated router(s), ideally two access points, DHCP pool of 200+, token pre-check before Start, pre-election load test |
| Phones using mobile data instead of Wi-Fi | Announce: turn off mobile data; stay connected to "no internet" Wi-Fi |

### Process controls
- Observers from each candidate's team present at setup, voting, and counting.
- Source code is short, readable, and reviewed by a teacher/IT staff before the election.
- Database is shown empty (no votes) at the start.
- **Paper ballots on standby** if the system fails.

---

## 11. Reconciliation, Results, and Export

### Reconciliation (before revealing results)
```
tokens issued (printed)   = tokens used + tokens unused
tokens used               = number of rows in votes
voter roll ticks          <= tokens issued
```
Any mismatch is reported to the observers before results are shown.

### Export
- `results.xlsx` / `results.csv`: candidate name and total votes only.
- Optional `ballots_shuffled.csv`: anonymous vote list in random order, for audit.
- `election.sqlite`: final database copy.
- `election.sqlite.sha256`: SHA-256 hash of the database file, read out/published so anyone can later verify integrity.
- Tokens table is never exported together with votes.

---

## 12. Testing Plan

| Test | Description | Pass criteria |
|---|---|---|
| Unit tests | Token generation, hashing, vote transaction, state checks | All pass |
| Double-vote test | Submit the same token twice concurrently | Exactly 1 vote recorded |
| State test | POST vote in IDLE/CLOSED | Rejected |
| Pre-check test | Check a valid token in IDLE, then vote after Open | Token not burned by the check; vote succeeds |
| Shared-token test | Pass the pre-check on two devices with one token, then vote from both | Exactly 1 vote recorded |
| Pre-check rate limit | Send many invalid token checks from one device | Lockout after the limit is reached |
| Start-burst test | 120 verified clients vote the instant Open is pressed | No errors; count = 120 |
| Restart test | Restart server while voters are waiting | Clients reconnect and can still vote with the same token |
| Admin isolation | Access `/admin/*` from another device on LAN | Denied |
| Load test | Script simulating 120 clients connecting and voting in parallel | No errors; count = 120 |
| Anonymity audit | Inspect DB, logs, exports for IP/time/order leaks | None found |
| Wi-Fi dry run | 30+ real phones (different brands/browsers) | All connect and vote |
| Failure drill | Kill server mid-vote, restart | State and votes preserved |
| Full rehearsal | Complete mock election with observers and paper roll | Reconciliation matches |

---

## 13. Election Day Checklist

**Setup (1 hour before)**
- [ ] Router powered, DHCP pool 200+, isolation off, offline
- [ ] Laptop on Ethernet, static IP set, plugged into power
- [ ] Sleep/lock/auto-update disabled; firewall rule active
- [ ] Server running; empty database shown to observers
- [ ] QR code and SSID/password posters displayed
- [ ] Token slips shuffled and boxed; voter roll ready
- [ ] Spare laptop and USB backup ready
- [ ] Paper ballots on standby

**During**
- [ ] Announce: turn off mobile data, connect to election Wi-Fi only
- [ ] Announce: open the URL and **enter your token before voting starts**; wait for the "Verified" screen
- [ ] Spare tokens available at the desk for slips that fail verification (record only the count of spares used)
- [ ] Open voting once most clients show verified; monitor "votes cast" counter
- [ ] Close at the announced time

**After**
- [ ] Reconcile counts with observers
- [ ] Reveal results
- [ ] Export, hash the DB, back up to USB
- [ ] Invalidate leftover tokens; shred paper slips as per policy

---

## 14. Milestones

| # | Milestone | Output |
|---|---|---|
| 1 | Get school approval; agree on rules with teachers and candidates | Written approval |
| 2 | Network setup and test (router, static IP, QR) | Working LAN |
| 3 | Backend prototype (state machine, tokens, vote endpoint) | Passing unit tests |
| 4 | Voter UI + WebSocket + admin panel | Working end-to-end demo |
| 5 | Anonymity audit and security review | Review notes |
| 6 | Load test and Wi-Fi dry run | Test report |
| 7 | Full rehearsal with observers | Sign-off |
| 8 | Election day | Results + exported files |
| 9 | Reflection and documentation | CAS evidence |

---

## 15. Decisions and Open Questions

### Resolved
| # | Topic | Decision |
|---|---|---|
| 1 | Number of candidates | **3 candidates** (3 buttons). |
| 2 | Voting schedule | **All 120 voters vote at once**, not in batches. |
| 3 | Router and laptop | **Resolved for now.** Will be arranged later by asking school IT (including whether they can lend an access point). |
| 4 | School approval | Required, but handled outside this spec. |
| 5 | Observers | **The Class Representative Council.** |
| 6 | Blank/abstain option | **None.** Voters choose one of the 3 candidates (decided 2026-10-13). |

### Open
None.

### Deferred
- Data retention policy after the election: to be decided later; not needed for the build.

### Impact of "all at once"
- The Wi-Fi is the main risk with 120 simultaneous clients, so two access points (if IT can lend one), a DHCP pool of 200+, and the load tests in section 12 are important.
- The token pre-check (section 6) helps here: tokens are verified while waiting, so the burst at Start is only 120 small vote requests.

---

## 16. CAS Reflection Prompts

- **Learning outcomes covered:** new skills (networking, security, databases), initiative and planning, collaboration, ethical decision-making.
- Document: your threat analysis, the decision to replace fingerprinting with tokens (and why), dry-run results, and what went wrong or surprised you.
- Reflect on the trade-off between convenience, security, and anonymity, and on the role of trust in the process.
