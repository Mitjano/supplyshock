-- SupplyShock commodity fork — vessel rerouting decisions
CREATE TABLE IF NOT EXISTS vessel_decision (
    decision_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id      INTEGER NOT NULL,
    mmsi          INTEGER,
    original_port TEXT,
    new_port      TEXT,
    reason        TEXT,
    created_at    DATETIME NOT NULL,
    FOREIGN KEY(agent_id) REFERENCES user(user_id)
);
