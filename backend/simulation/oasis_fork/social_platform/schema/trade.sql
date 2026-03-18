-- SupplyShock commodity fork — trade decisions table
CREATE TABLE IF NOT EXISTS trade (
    trade_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id   INTEGER NOT NULL,
    commodity  TEXT NOT NULL,
    action     TEXT NOT NULL,
    volume_mt  REAL DEFAULT 0,
    price_view REAL,
    created_at DATETIME NOT NULL,
    FOREIGN KEY(agent_id) REFERENCES user(user_id)
);
CREATE INDEX IF NOT EXISTS idx_trade_commodity ON trade(commodity);
CREATE INDEX IF NOT EXISTS idx_trade_agent ON trade(agent_id);
