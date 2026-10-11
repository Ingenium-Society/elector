-- ANONYMITY RULES: the votes table must never get a timestamp, a token
-- reference, an IP address, or device info. Do not add such columns.

CREATE TABLE IF NOT EXISTS config (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidates (
  id   INTEGER PRIMARY KEY,
  name TEXT NOT NULL
);

-- Only a hash of each token is stored, plus a used flag. No "used at" time.
CREATE TABLE IF NOT EXISTS tokens (
  token_hash TEXT PRIMARY KEY,
  used       INTEGER NOT NULL DEFAULT 0
);

-- Anonymous ballots: a random ID and the chosen candidate, nothing else.
CREATE TABLE IF NOT EXISTS votes (
  id           TEXT PRIMARY KEY,
  candidate_id INTEGER NOT NULL REFERENCES candidates(id)
) WITHOUT ROWID;
