"""Price discovery utilities for commodity simulation.

Aggregates agent price views from market_state table
to compute the emergent market consensus price.
"""

import sqlite3
from typing import Any, Optional


def compute_consensus_price(
    commodity: str, db_path: str, last_n_steps: int = 1
) -> Optional[float]:
    """Compute consensus market price from agent price views.

    Aggregates weighted AVG(price_view) from market_state table.
    This is the emergent market price — not set by the simulation,
    but discovered through agent decisions.

    Args:
        commodity: Commodity to aggregate (coal, crude_oil, etc.)
        db_path: Path to OASIS SQLite database.
        last_n_steps: Number of recent timesteps to include.

    Returns:
        float: Weighted average price view, or None if no data.
    """
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    ROUND(SUM(ms.price_view * ms.confidence) / SUM(ms.confidence), 2) as weighted_avg,
                    COUNT(*) as num_views,
                    MIN(ms.price_view) as low,
                    MAX(ms.price_view) as high
                FROM (
                    SELECT price_view, confidence
                    FROM market_state
                    WHERE commodity = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                ) ms
                """,
                (commodity, last_n_steps * 100),
            )
            row = cursor.fetchone()
        if row and row[0]:
            return float(row[0])
        return None
    except Exception:
        return None


def get_simulation_summary(db_path: str) -> dict[str, Any]:
    """Generate post-simulation summary from SQLite database.

    Used by ReportAgent to build narrative PDF report.

    Args:
        db_path: Path to OASIS SQLite database.

    Returns:
        dict with keys: trade_counts, price_evolution, reroutes, measures.
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Trade action distribution
        cursor.execute(
            """
            SELECT commodity, action, COUNT(*) as n, AVG(price_view) as avg_price
            FROM trade GROUP BY commodity, action ORDER BY n DESC
            """
        )
        trade_counts = [
            {"commodity": r[0], "action": r[1], "count": r[2], "avg_price": r[3]}
            for r in cursor.fetchall()
        ]

        # Price evolution over time
        cursor.execute(
            """
            SELECT commodity, ROUND(AVG(price_view), 2) as avg_price, created_at
            FROM market_state GROUP BY commodity, DATE(created_at)
            ORDER BY created_at
            """
        )
        price_evolution = [
            {"commodity": r[0], "price": r[1], "at": r[2]}
            for r in cursor.fetchall()
        ]

        # Vessel reroutes
        cursor.execute(
            "SELECT new_port, reason, COUNT(*) as n FROM vessel_decision GROUP BY new_port, reason"
        )
        reroutes = [
            {"port": r[0], "reason": r[1], "count": r[2]}
            for r in cursor.fetchall()
        ]

        # Government measures
        cursor.execute(
            "SELECT info FROM trace WHERE action = 'impose_measure'"
        )
        measures = [r[0] for r in cursor.fetchall()]

    return {
        "trade_counts": trade_counts,
        "price_evolution": price_evolution,
        "reroutes": reroutes,
        "measures": measures,
    }
