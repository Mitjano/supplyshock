"""Platform utility functions — trace recording and recommendation system."""

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class PlatformUtils:
    """Utility class for platform operations."""

    def __init__(self, db: sqlite3.Connection, cursor: sqlite3.Cursor):
        self.db = db
        self.db_cursor = cursor

    def _record_trace(
        self, agent_id: int, action: str, info: dict[str, Any], created_at: datetime
    ) -> None:
        """Record action trace to SQLite for audit trail."""
        try:
            self.db_cursor.execute(
                "INSERT INTO trace (agent_id, action, info, created_at) VALUES (?,?,?,?)",
                (agent_id, action, json.dumps(info), created_at),
            )
            self.db.commit()
        except Exception as e:
            logger.error("Failed to record trace for agent %d: %s", agent_id, e)

    def get_recommended_posts(
        self, agent_id: int, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get recent posts for agent's feed (recommendation system).

        For commodity platform, posts are market events seeded by ManualAction.
        """
        try:
            self.db_cursor.execute(
                """SELECT post_id, user_id, content, created_at
                   FROM post
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (limit,),
            )
            rows = self.db_cursor.fetchall()
            return [
                {
                    "post_id": r[0],
                    "user_id": r[1],
                    "content": r[2],
                    "created_at": r[3],
                }
                for r in rows
            ]
        except Exception as e:
            logger.error("Failed to get recommended posts: %s", e)
            return []
