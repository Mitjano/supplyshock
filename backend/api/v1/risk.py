"""Risk/conflict endpoints — /api/v1/risk/* (Issue #79)

- GET /risk/conflicts — conflict events near infrastructure from GDELT
"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/risk", tags=["Risk"])


@router.get("/conflicts")
async def get_conflict_events(
    region: str = Query(None, description="Region: middle_east, east_asia, europe, africa_horn, south_asia, southeast_asia, black_sea"),
    days: int = Query(30, ge=1, le=365, description="Number of days of history"),
    severity: str = Query(None, description="Filter by severity: low, medium, high, critical"),
    event_type: str = Query(None, description="Filter: armed_conflict, blockade, protest, military_activity"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Conflict events near critical infrastructure from GDELT.

    Returns geolocated conflict events classified by type and severity,
    with aggregated statistics per region.
    """
    conditions = [f"event_date >= CURRENT_DATE - INTERVAL '{days} days'"]
    params: dict[str, Any] = {}

    if region:
        conditions.append("region = :region")
        params["region"] = region

    if severity:
        conditions.append("severity = :severity")
        params["severity"] = severity

    if event_type:
        conditions.append("event_type = :event_type")
        params["event_type"] = event_type

    where = " AND ".join(conditions)

    # Fetch events
    result = await db.execute(
        text(f"""
            SELECT event_date, region, latitude, longitude, event_type,
                   severity, title, source_url, goldstein_scale, num_mentions
            FROM conflict_events
            WHERE {where}
            ORDER BY event_date DESC, num_mentions DESC
            LIMIT 500
        """),
        params,
    )
    rows = result.mappings().all()

    events = [
        {
            "date": str(r["event_date"]),
            "region": r["region"],
            "lat": r["latitude"],
            "lon": r["longitude"],
            "type": r["event_type"],
            "severity": r["severity"],
            "title": r["title"],
            "source_url": r["source_url"],
            "goldstein_scale": r["goldstein_scale"],
            "mentions": r["num_mentions"],
        }
        for r in rows
    ]

    # Aggregate by region
    result_agg = await db.execute(
        text(f"""
            SELECT region,
                   COUNT(*) as event_count,
                   COUNT(*) FILTER (WHERE severity IN ('high', 'critical')) as high_severity_count,
                   AVG(goldstein_scale) as avg_goldstein,
                   SUM(num_mentions) as total_mentions
            FROM conflict_events
            WHERE {where}
            GROUP BY region
            ORDER BY event_count DESC
        """),
        params,
    )
    agg_rows = result_agg.mappings().all()

    region_summary = {
        r["region"]: {
            "event_count": r["event_count"],
            "high_severity_count": r["high_severity_count"],
            "avg_goldstein": round(float(r["avg_goldstein"]), 2) if r["avg_goldstein"] else None,
            "total_mentions": r["total_mentions"],
            "risk_level": (
                "critical" if r["high_severity_count"] > 10
                else "high" if r["high_severity_count"] > 3
                else "elevated" if r["event_count"] > 10
                else "normal"
            ),
        }
        for r in agg_rows
    }

    return {
        "data": events,
        "region_summary": region_summary,
        "days": days,
        "total_events": len(events),
    }
