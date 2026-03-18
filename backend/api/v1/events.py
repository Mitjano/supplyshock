"""Historical event replay endpoints — /api/v1/events/*

- GET /events             — list all historical events
- GET /events/{id}/replay — replay an event with price impact data
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/events", tags=["Events"])


@router.get("")
async def list_events(
    region: str | None = Query(None, description="Filter by region"),
    commodity: str | None = Query(None, description="Filter by commodity"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """List all historical supply-chain events."""
    query = "SELECT * FROM historical_events WHERE 1=1"
    params: dict[str, Any] = {}

    if region:
        query += " AND region ILIKE :region"
        params["region"] = f"%{region}%"

    if commodity:
        query += " AND commodities ILIKE :commodity"
        params["commodity"] = f"%{commodity}%"

    query += " ORDER BY event_date DESC"

    result = await db.execute(text(query), params)
    rows = result.mappings().all()

    return {
        "data": [
            {
                "id": str(row["id"]),
                "slug": row["slug"],
                "title": row["title"],
                "description": row["description"],
                "event_date": row["event_date"].isoformat() if row["event_date"] else None,
                "end_date": row["end_date"].isoformat() if row.get("end_date") else None,
                "region": row["region"],
                "commodities": row["commodities"].split(",") if row["commodities"] else [],
                "impact_summary": row["impact_summary"],
            }
            for row in rows
        ],
    }


@router.get("/{event_id}/replay")
async def replay_event(
    event_id: str,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Replay a historical event with price data before/after and impact analysis."""
    # Fetch the event
    ev_result = await db.execute(
        text("SELECT * FROM historical_events WHERE id = :eid"),
        {"eid": event_id},
    )
    event = ev_result.mappings().first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    commodities = event["commodities"].split(",") if event["commodities"] else []
    event_date = event["event_date"]

    # Fetch price snapshots around the event for each commodity
    price_impacts = []
    for commodity in commodities:
        commodity = commodity.strip()

        # Price 7 days before the event
        before_result = await db.execute(
            text("""
                SELECT price, recorded_at FROM commodity_prices
                WHERE commodity = :commodity
                  AND recorded_at <= :event_date
                ORDER BY recorded_at DESC
                LIMIT 1
            """),
            {"commodity": commodity, "event_date": event_date},
        )
        before = before_result.mappings().first()

        # Price 7 days after the event (or end_date if available)
        after_date = event.get("end_date") or event_date
        after_result = await db.execute(
            text("""
                SELECT price, recorded_at FROM commodity_prices
                WHERE commodity = :commodity
                  AND recorded_at >= :after_date
                ORDER BY recorded_at ASC
                LIMIT 1
            """),
            {"commodity": commodity, "after_date": after_date},
        )
        after = after_result.mappings().first()

        impact = {
            "commodity": commodity,
            "price_before": float(before["price"]) if before else None,
            "price_after": float(after["price"]) if after else None,
            "date_before": before["recorded_at"].isoformat() if before else None,
            "date_after": after["recorded_at"].isoformat() if after else None,
            "impact_pct": None,
        }

        if before and after and float(before["price"]) > 0:
            impact["impact_pct"] = round(
                ((float(after["price"]) - float(before["price"])) / float(before["price"])) * 100,
                2,
            )

        price_impacts.append(impact)

    return {
        "data": {
            "event": {
                "id": str(event["id"]),
                "slug": event["slug"],
                "title": event["title"],
                "description": event["description"],
                "event_date": event["event_date"].isoformat() if event["event_date"] else None,
                "end_date": event["end_date"].isoformat() if event.get("end_date") else None,
                "region": event["region"],
                "impact_summary": event["impact_summary"],
            },
            "price_impacts": price_impacts,
        },
    }
