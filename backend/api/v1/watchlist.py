"""Watchlist endpoints — /api/v1/watchlist

- POST   /watchlist          — add commodity to watchlist
- GET    /watchlist          — get user's watchlist with prices & 7d sparkline
- DELETE /watchlist/{commodity} — remove commodity from watchlist
"""

from typing import Any

from fastapi import APIRouter, Depends, Query, Path, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db, resolve_user_id
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/watchlist", tags=["Watchlist"])


class WatchlistAdd(BaseModel):
    commodity: str


@router.post("")
async def add_to_watchlist(
    body: WatchlistAdd,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Add a commodity to the user's watchlist."""
    user_id = await resolve_user_id(user, db)

    await db.execute(
        text("""
            INSERT INTO user_watchlist (user_id, commodity)
            VALUES (:user_id, :commodity)
            ON CONFLICT (user_id, commodity) DO NOTHING
        """),
        {"user_id": user_id, "commodity": body.commodity},
    )
    await db.commit()
    return {"status": "ok", "commodity": body.commodity}


@router.get("")
async def get_watchlist(
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Get user's watchlist with latest prices and 7-day sparkline data."""
    user_id = await resolve_user_id(user, db)

    # Get watchlist commodities with latest price
    result = await db.execute(
        text("""
            SELECT w.commodity,
                   cp.price, cp.unit, cp.change_24h, cp.benchmark,
                   cp.time AS price_time
            FROM user_watchlist w
            LEFT JOIN LATERAL (
                SELECT price, unit, change_24h, benchmark, time
                FROM commodity_prices
                WHERE commodity = w.commodity
                ORDER BY time DESC
                LIMIT 1
            ) cp ON TRUE
            WHERE w.user_id = :user_id
            ORDER BY w.created_at DESC
        """),
        {"user_id": user_id},
    )
    rows = result.mappings().all()

    items = []
    for r in rows:
        # Fetch 7-day sparkline (daily close prices)
        sparkline_result = await db.execute(
            text("""
                SELECT time_bucket('1 day', time) AS day, last(price, time) AS close
                FROM commodity_prices
                WHERE commodity = :commodity
                  AND time > NOW() - INTERVAL '7 days'
                GROUP BY day
                ORDER BY day ASC
            """),
            {"commodity": r["commodity"]},
        )
        sparkline = [float(s["close"]) for s in sparkline_result.mappings().all()]

        items.append({
            "commodity": r["commodity"],
            "price": float(r["price"]) if r["price"] else None,
            "unit": r["unit"],
            "change_24h": float(r["change_24h"]) if r["change_24h"] is not None else None,
            "benchmark": r["benchmark"],
            "price_time": r["price_time"].isoformat() if r["price_time"] else None,
            "sparkline_7d": sparkline,
        })

    return {"data": items, "meta": {"total": len(items)}}


@router.delete("/{commodity}")
async def remove_from_watchlist(
    commodity: str = Path(..., description="Commodity to remove"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Remove a commodity from the user's watchlist."""
    user_id = await resolve_user_id(user, db)

    result = await db.execute(
        text("""
            DELETE FROM user_watchlist
            WHERE user_id = :user_id AND commodity = :commodity
        """),
        {"user_id": user_id, "commodity": commodity},
    )
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Commodity not in watchlist")

    return {"status": "ok", "commodity": commodity}
