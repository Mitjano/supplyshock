"""SQLite database creation for OASIS commodity fork.

Creates all required tables: OASIS core (user, post, trace, etc.)
plus commodity extension tables (trade, market_state, vessel_decision).
"""

import logging
import os
import os.path as osp
import sqlite3

logger = logging.getLogger(__name__)


def create_db(db_path: str) -> tuple[sqlite3.Connection, sqlite3.Cursor]:
    """Create SQLite database with all required tables.

    Args:
        db_path: Path to SQLite database file.

    Returns:
        Tuple of (connection, cursor).
    """
    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # ── Core OASIS tables ──────────────────────────────────────
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS user (
            user_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name  TEXT NOT NULL,
            name       TEXT DEFAULT '',
            bio        TEXT DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            num_followings INTEGER DEFAULT 0,
            num_followers  INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS post (
            post_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            content    TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            num_likes      INTEGER DEFAULT 0,
            num_dislikes   INTEGER DEFAULT 0,
            num_comments   INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES user(user_id)
        );
        CREATE INDEX IF NOT EXISTS idx_post_user ON post(user_id);
        CREATE INDEX IF NOT EXISTS idx_post_created ON post(created_at);

        CREATE TABLE IF NOT EXISTS comment (
            comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id    INTEGER NOT NULL,
            user_id    INTEGER NOT NULL,
            content    TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            num_likes      INTEGER DEFAULT 0,
            num_dislikes   INTEGER DEFAULT 0,
            FOREIGN KEY(post_id) REFERENCES post(post_id),
            FOREIGN KEY(user_id) REFERENCES user(user_id)
        );

        CREATE TABLE IF NOT EXISTS follow (
            follower_id INTEGER NOT NULL,
            followee_id INTEGER NOT NULL,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(follower_id, followee_id),
            FOREIGN KEY(follower_id) REFERENCES user(user_id),
            FOREIGN KEY(followee_id) REFERENCES user(user_id)
        );

        CREATE TABLE IF NOT EXISTS like_post (
            user_id INTEGER NOT NULL,
            post_id INTEGER NOT NULL,
            PRIMARY KEY(user_id, post_id)
        );

        CREATE TABLE IF NOT EXISTS dislike_post (
            user_id INTEGER NOT NULL,
            post_id INTEGER NOT NULL,
            PRIMARY KEY(user_id, post_id)
        );

        CREATE TABLE IF NOT EXISTS mute (
            user_id       INTEGER NOT NULL,
            muted_user_id INTEGER NOT NULL,
            PRIMARY KEY(user_id, muted_user_id)
        );

        CREATE TABLE IF NOT EXISTS trace (
            trace_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id   INTEGER NOT NULL,
            action     TEXT NOT NULL,
            info       TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_trace_agent ON trace(agent_id);
        CREATE INDEX IF NOT EXISTS idx_trace_action ON trace(action);

        CREATE TABLE IF NOT EXISTS product (
            product_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            name        TEXT NOT NULL,
            description TEXT DEFAULT '',
            price       REAL DEFAULT 0,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES user(user_id)
        );

        CREATE TABLE IF NOT EXISTS message (
            message_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id   INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            content     TEXT NOT NULL,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(sender_id) REFERENCES user(user_id),
            FOREIGN KEY(receiver_id) REFERENCES user(user_id)
        );
    """)

    # ── Commodity extension tables (SupplyShock fork) ──────────
    # Graceful — nie crashuje jeśli pliki nie istnieją (np. w testach OASIS)
    schema_dir = osp.join(osp.dirname(__file__), "schema")
    for schema_file in ["trade.sql", "market_state.sql", "vessel_decision.sql"]:
        schema_path = osp.join(schema_dir, schema_file)
        if osp.exists(schema_path):
            with open(schema_path, "r") as sql_file:
                cursor.executescript(sql_file.read())
            logger.debug("Loaded commodity schema: %s", schema_file)

    conn.commit()
    return conn, cursor
