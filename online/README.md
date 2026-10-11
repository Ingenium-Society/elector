# online/: hosted version (experimental, not started)

This folder is for an **online** version of the election app (for example a
Supabase database with a hosted front end). It is **a demo and experiment only**.
**The real election uses `offline/`.**

**Status:** no code yet. Nothing here is built, and nothing here is promised.

## Rules for this folder

- **Fake data only.** Use dummy tokens and made-up candidates. Never put real
  election data, real tokens, or real votes here.
- **Never commit secrets.** Supabase URLs and keys go in a `.env` file, which
  `.gitignore` blocks. Never expose the Supabase *service* key to a browser.
- **Do not copy code between `offline/` and `online/` silently.** If a change is
  needed in both, make two small pull requests and say so in each.
- The anonymity rules in `AGENTS.md` still apply as far as the platform allows.
  Where the platform cannot meet a rule, write it down in the table below.

## Why this is not the election version

| Topic | `offline/` (real election) | `online/` (demo) |
|---|---|---|
| Where voting happens | In the room, supervised | Anywhere with internet |
| Server and data | One laptop; observers can inspect it | A third-party host |
| Logs | Access logging for the vote endpoint switched off | Platform logs IPs and times and we cannot switch that off |
| Row order | `WITHOUT ROWID` plus shuffled exports | Postgres keeps rough insertion order; shuffle on export |
| Network | Dedicated router, no internet | Depends on the school's internet |
| Vote buying or coercion | Reduced by voting in the room | Possible, because voting is remote |

## Ideas, not decisions

Rough shape if this gets built (see the online track in `docs/ROADMAP.md`):

- Postgres tables like `offline/app/schema.sql`.
- One database function, e.g. `cast_vote(token, candidate)`, that checks the state,
  burns the token and inserts the anonymous vote in a single transaction.
- Row Level Security so voters cannot read or write the tables directly.
- Supabase Realtime to tell voters when voting opens.
- Token hashes made with a secret key (HMAC), not a plain SHA-256.
- Vercel is a poor fit for a server that keeps state. Use a host that runs a
  normal always-on process, or put the logic in the database and keep the front end static.
