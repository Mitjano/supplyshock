"""Sentiment endpoints — /api/v1/sentiment/*

- GET /sentiment/trends   — Google Trends search interest for commodities

Issue #89
"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/sentiment", tags=["Sentiment"])


@router.get("/trends")
async def get_trends(
    keywords: str = Query(
        "oil_price",
        description="Comma-separated trend indicators (e.g. oil_price,gold_price)",
    ),
    days: int = Query(30, ge=1, le=365, description="Number of days of history"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Google Trends search interest data for commodity keywords."""
    keyword_list = [f"gtrends_{k.strip()}" for k in keywords.split(",")]

    result = await db.execute(
        text(f"""
            SELECT indicator, time, value, unit, source
            FROM macro_indicators
            WHERE indicator = ANY(:indicators)
              AND source = 'google_trends'
              AND time >= NOW() - INTERVAL '{days} days'
            ORDER BY indicator, time DESC
        """),
        {"indicators": keyword_list},
    )
    rows = result.mappings().all()

    # Group by keyword
    grouped: dict[str, list] = {}
    for r in rows:
        key = r["indicator"].replace("gtrends_", "")
        if key not in grouped:
            grouped[key] = []
        grouped[key].append({
            "time": r["time"].isoformat() if hasattr(r["time"], "isoformat") else str(r["time"]),
            "value": r["value"],
        })

    return {"data": grouped, "keywords": keywords, "days": days}
