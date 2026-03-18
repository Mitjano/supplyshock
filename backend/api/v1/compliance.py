"""Compliance endpoints — /api/v1/compliance/*

- GET /compliance/sanctions   — screen a vessel against sanctions lists
- GET /compliance/flagged     — list all flagged (sanctioned) vessels
- GET /compliance/ais-gaps    — recent AIS gap events
- GET /compliance/sts-events  — recent STS transfer events
- GET /compliance/spoofing    — recent spoofing events
"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from compliance.screening import screen_vessel
from dependencies import get_db, get_redis
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/compliance", tags=["Compliance"])


@router.get("/sanctions")
async def check_sanctions(
    mmsi: int = Query(..., description="Vessel MMSI"),
    imo: int | None = Query(None, description="Vessel IMO number"),
    name: str | None = Query(None, description="Vessel name for fuzzy matching"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Screen a vessel against OFAC and EU sanctions lists."""
    result = await screen_vessel(db, mmsi=mmsi, imo=imo, name=name)
    return {"data": result}


@router.get("/flagged")
async def list_flagged_vessels(
    source: str | None = Query(None, description="Filter by source: ofac, eu"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """List all sanctioned vessel entities."""
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit": limit, "offset": offset}

    if source:
        conditions.append("source = :source")
        params["source"] = source

    where = " AND ".join(conditions)

    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM sanctioned_entities WHERE {where}"), params
    )
    total = count_result.scalar()

    result = await db.execute(
        text(f"""
            SELECT id, source, entity_name, program, imo, mmsi,
                   flag, vessel_type, remarks, updated_at
            FROM sanctioned_entities
            WHERE {where}
            ORDER BY updated_at DESC
            LIMIT :limit OFFSET :offset
        """),
        params,
    )
    rows = result.mappings().all()

    return {
        "data": [
            {
                "id": r["id"],
                "source": r["source"],
                "entity_name": r["entity_name"],
                "program": r["program"],
                "imo": r["imo"],
                "mmsi": r["mmsi"],
                "flag": r["flag"],
                "vessel_type": r["vessel_type"],
                "remarks": r["remarks"],
                "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
            }
            for r in rows
        ],
        "meta": {"total": total, "offset": offset, "limit": limit},
    }


@router.get("/ais-gaps")
async def list_ais_gaps(
    hours: int = Query(24, le=168, description="Lookback hours"),
    mmsi: int | None = Query(None, description="Filter by MMSI"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """List AIS gap alert events."""
    return await _list_compliance_alerts(db, "ais_gap", hours, mmsi, offset, limit)


@router.get("/sts-events")
async def list_sts_events(
    hours: int = Query(48, le=168, description="Lookback hours"),
    mmsi: int | None = Query(None, description="Filter by MMSI"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """List ship-to-ship transfer alert events."""
    return await _list_compliance_alerts(db, "sts_transfer", hours, mmsi, offset, limit)


@router.get("/spoofing")
async def list_spoofing_events(
    hours: int = Query(24, le=168, description="Lookback hours"),
    mmsi: int | None = Query(None, description="Filter by MMSI"),
    subtype: str | None = Query(None, description="Filter: teleportation, impossible_speed"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """List AIS spoofing alert events."""
    conditions = [
        "type = :type",
        "time > NOW() - make_interval(hours => :hours)",
    ]
    params: dict[str, Any] = {
        "type": "ais_spoofing",
        "hours": hours,
        "limit": limit,
        "offset": offset,
    }

    if mmsi:
        conditions.append("mmsi = :mmsi")
        params["mmsi"] = mmsi
    if subtype:
        conditions.append("metadata->>'subtype' = :subtype")
        params["subtype"] = subtype

    where = " AND ".join(conditions)

    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM alert_events WHERE {where}"), params
    )
    total = count_result.scalar()

    result = await db.execute(
        text(f"""
            SELECT id, time, type, severity, title, body, mmsi, metadata, is_active
            FROM alert_events
            WHERE {where}
            ORDER BY time DESC
            LIMIT :limit OFFSET :offset
        """),
        params,
    )
    rows = result.mappings().all()

    return {
        "data": [_format_alert(r) for r in rows],
        "meta": {"total": total, "offset": offset, "limit": limit},
    }


async def _list_compliance_alerts(
    db: AsyncSession,
    alert_type: str,
    hours: int,
    mmsi: int | None,
    offset: int,
    limit: int,
) -> dict:
    """Shared helper for listing compliance alert events by type."""
    conditions = [
        "type = :type",
        "time > NOW() - make_interval(hours => :hours)",
    ]
    params: dict[str, Any] = {
        "type": alert_type,
        "hours": hours,
        "limit": limit,
        "offset": offset,
    }

    if mmsi:
        conditions.append("mmsi = :mmsi")
        params["mmsi"] = mmsi

    where = " AND ".join(conditions)

    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM alert_events WHERE {where}"), params
    )
    total = count_result.scalar()

    result = await db.execute(
        text(f"""
            SELECT id, time, type, severity, title, body, mmsi, metadata, is_active
            FROM alert_events
            WHERE {where}
            ORDER BY time DESC
            LIMIT :limit OFFSET :offset
        """),
        params,
    )
    rows = result.mappings().all()

    return {
        "data": [_format_alert(r) for r in rows],
        "meta": {"total": total, "offset": offset, "limit": limit},
    }


def _format_alert(r) -> dict:
    """Format an alert_events row for JSON response."""
    return {
        "id": str(r["id"]),
        "time": r["time"].isoformat(),
        "type": r["type"],
        "severity": r["severity"],
        "title": r["title"],
        "body": r["body"],
        "mmsi": r["mmsi"],
        "metadata": r["metadata"],
        "is_active": r["is_active"],
    }
