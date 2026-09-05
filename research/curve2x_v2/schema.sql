-- CURVE2X V2 paper-only state (SQLite). Fara chei, fara tranzactii.
CREATE TABLE IF NOT EXISTS signals(
  mint TEXT NOT NULL, landmark INTEGER NOT NULL, ts INTEGER NOT NULL, action TEXT NOT NULL CHECK(action IN ('REJECT','WATCH','PAPER_CANDIDATE')),
  reason TEXT, p_tp REAL, p_sl REAL, p_to REAL, ev REAL, ev_lcb REAL, model_hash TEXT NOT NULL, created_at REAL DEFAULT (strftime('%s','now')),
  PRIMARY KEY(mint, landmark, action));
CREATE UNIQUE INDEX IF NOT EXISTS one_candidate_per_mint ON signals(mint) WHERE action='PAPER_CANDIDATE';
CREATE TABLE IF NOT EXISTS checkpoint(id INTEGER PRIMARY KEY CHECK(id=1), file TEXT, seq INTEGER);
