-- SupplyShock commodity fork — price consensus per timestep
CREATE TABLE IF NOT EXISTS market_state (
    state_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    commodity  TEXT NOT NULL,
    agent_id   INTEGER,
    price_view REAL NOT NULL,
    confidence REAL DEFAULT 1.0,
    timestep   INTEGER DEFAULT 0,
    created_at DATETIME NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ms_commodity ON market_state(commodity, created_at);
