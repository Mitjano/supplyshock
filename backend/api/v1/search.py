"""Global search — /api/v1/search

Searches across vessels, ports, commodities, and chokepoints using pg_trgm fuzzy matching.
"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("")
async def global_search(
    q: str = Query(..., min_length=1, max_length=200, description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Search across all entity types. Returns categorized results."""
    query = q.strip()
    params = {"q": query, "like": f"%{query}%", "limit": limit}

    results: dict[str, list] = {
        "vessels": [],
        "ports": [],
        "commodities": [],
        "chokepoints": [],
        "events": [],
    }

    # Vessels: search by name, MMSI, IMO
    vessel_result = await db.execute(
        text("""
            SELECT DISTINCT ON (mmsi) mmsi, vessel_name, vessel_type, imo_number
            FROM vessel_positions
            WHERE vessel_name ILIKE :like
               OR mmsi::TEXT = :q
               OR imo_number::TEXT = :q
            ORDER BY mmsi, time DESC
            LIMIT :limit
        """),
        params,
    )
    for r in vessel_result.mappings().all():
        results["vessels"].append({
            "mmsi": r["mmsi"],
            "name": r["vessel_name"],
            "type": r["vessel_type"],
            "imo": r["imo_number"],
        })

    # Ports: search by name, country_code
    port_result = await db.execute(
        text("""
            SELECT id, name, country_code, latitude, longitude, is_major
            FROM ports
            WHERE name ILIKE :like OR country_code ILIKE :q
            ORDER BY is_major DESC, name ASC
            LIMIT :limit
        """),
        params,
    )
    for r in port_result.mappings().all():
        results["ports"].append({
            "id": str(r["id"]),
            "name": r["name"],
            "country_code": r["country_code"],
            "latitude": float(r["latitude"]),
            "longitude": float(r["longitude"]),
            "is_major": r["is_major"],
        })

    # Chokepoints: search by name, slug
    chokepoint_result = await db.execute(
        text("""
            SELECT id, slug, name, latitude, longitude, baseline_risk
            FROM bottleneck_nodes
            WHERE name ILIKE :like OR slug ILIKE :like
            ORDER BY name ASC
            LIMIT :limit
        """),
        params,
    )
    for r in chokepoint_result.mappings().all():
        results["chokepoints"].append({
            "id": str(r["id"]),
            "slug": r["slug"],
            "name": r["name"],
            "latitude": float(r["latitude"]) if r["latitude"] else None,
            "longitude": float(r["longitude"]) if r["longitude"] else None,
            "baseline_risk": r["baseline_risk"],
        })

    # Commodities: search from commodity_prices distinct commodities
    commodity_result = await db.execute(
        text("""
            SELECT DISTINCT commodity, benchmark
            FROM commodity_prices
            WHERE commodity ILIKE :like OR benchmark ILIKE :like
            ORDER BY commodity ASC
            LIMIT :limit
        """),
        params,
    )
    for r in commodity_result.mappings().all():
        results["commodities"].append({
            "commodity": r["commodity"],
            "benchmark": r["benchmark"],
        })

    # Events: search alert titles
    event_result = await db.execute(
        text("""
            SELECT id, title, type, severity, commodity, time
            FROM alert_events
            WHERE title ILIKE :like
            ORDER BY time DESC
            LIMIT :limit
        """),
        params,
    )
    for r in event_result.mappings().all():
        results["events"].append({
            "id": str(r["id"]),
            "title": r["title"],
            "type": r["type"],
            "severity": r["severity"],
            "commodity": r["commodity"],
            "time": r["time"].isoformat() if r["time"] else None,
        })

    total = sum(len(v) for v in results.values())
    return {"query": query, "total": total, "results": results}
