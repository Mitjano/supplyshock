"""Vessel endpoints — /api/v1/vessels/*

- GET  /vessels          — live vessel positions (bbox + type filter)
- GET  /vessels/{mmsi}   — full vessel detail
- GET  /vessels/{mmsi}/trail — vessel trail (last N hours)
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db
from middleware.auth import require_auth
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/vessels", tags=["Vessels"])


@router.get("")
async def list_vessels(
    bbox: str | None = Query(None, description="min_lng,min_lat,max_lng,max_lat"),
    vessel_type: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(500, le=5000),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Get current vessel positions for the map viewport.

    Uses latest_vessel_positions materialized view for performance.
    Falls back to direct query if view doesn't exist yet.
    """
    conditions = []
    params: dict[str, Any] = {"limit": limit}

    if bbox:
        parts = bbox.split(",")
        if len(parts) != 4:
            raise HTTPException(status_code=400, detail={"error": "Invalid bbox format — expected min_lng,min_lat,max_lng,max_lat", "code": "INVALID_BBOX"})
        try:
            min_lng, min_lat, max_lng, max_lat = [float(p) for p in parts]
            conditions.append("latitude BETWEEN :min_lat AND :max_lat")
            conditions.append("longitude BETWEEN :min_lng AND :max_lng")
            params.update(min_lat=min_lat, max_lat=max_lat, min_lng=min_lng, max_lng=max_lng)
        except ValueError:
            raise HTTPException(status_code=400, detail={"error": "Invalid bbox values — expected numbers", "code": "INVALID_BBOX"})

    if vessel_type:
        conditions.append("vessel_type = :vessel_type")
        params["vessel_type"] = vessel_type

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    params["offset"] = offset

    # Get total count
    try:
        count_result = await db.execute(
            text(f"SELECT COUNT(*) FROM latest_vessel_positions {where}"),
            params,
        )
        total = count_result.scalar()
    except Exception:
        count_result = await db.execute(
            text(f"""
                SELECT COUNT(*) FROM (
                    SELECT DISTINCT ON (mmsi) mmsi
                    FROM vessel_positions
                    WHERE time > NOW() - INTERVAL '2 hours'
                ) sub
                {where}
            """),
            params,
        )
        total = count_result.scalar()

    # Try materialized view first, fall back to subquery
    try:
        result = await db.execute(
            text(f"""
                SELECT mmsi, imo, vessel_name, vessel_type, latitude, longitude,
                       speed_knots, course, destination, flag_country, time
                FROM latest_vessel_positions
                {where}
                LIMIT :limit OFFSET :offset
            """),
            params,
        )
    except Exception:
        # Materialized view doesn't exist yet — use window function fallback
        result = await db.execute(
            text(f"""
                SELECT mmsi, imo, vessel_name, vessel_type, latitude, longitude,
                       speed_knots, course, destination, flag_country, time
                FROM (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY mmsi ORDER BY time DESC) as rn
                    FROM vessel_positions
                    WHERE time > NOW() - INTERVAL '2 hours'
                ) sub
                WHERE rn = 1
                {' AND ' + ' AND '.join(conditions) if conditions else ''}
                LIMIT :limit OFFSET :offset
            """),
            params,
        )

    rows = result.mappings().all()

    return {
        "data": [
            {
                "mmsi": row["mmsi"],
                "imo": row["imo"],
                "vessel_name": row["vessel_name"],
                "vessel_type": row["vessel_type"],
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "speed_knots": float(row["speed_knots"]) if row["speed_knots"] else None,
                "course": float(row["course"]) if row["course"] else None,
                "destination": row["destination"],
                "flag_country": row["flag_country"],
                "time": row["time"].isoformat(),
            }
            for row in rows
        ],
        "meta": {"total": total, "offset": offset, "limit": limit},
    }


@router.get("/{mmsi}")
async def get_vessel_detail(
    mmsi: int,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Get full vessel details by MMSI.

    Returns 404 if vessel hasn't been seen in the last 2 hours.
    """
    result = await db.execute(
        text("""
            SELECT mmsi, imo, vessel_name, vessel_type, latitude, longitude,
                   speed_knots, course, heading, destination, eta, draught,
                   flag_country, cargo_type, time
            FROM vessel_positions
            WHERE mmsi = :mmsi AND time > NOW() - INTERVAL '2 hours'
            ORDER BY time DESC
            LIMIT 1
        """),
        {"mmsi": mmsi},
    )
    row = result.mappings().first()

    if not row:
        raise HTTPException(
            status_code=404,
            detail={"error": "Vessel not found in last 2 hours", "code": "VESSEL_NOT_FOUND"},
        )

    return {
        "data": {
            "mmsi": row["mmsi"],
            "imo": row["imo"],
            "vessel_name": row["vessel_name"],
            "vessel_type": row["vessel_type"],
            "latitude": float(row["latitude"]),
            "longitude": float(row["longitude"]),
            "speed_knots": float(row["speed_knots"]) if row["speed_knots"] else None,
            "course": float(row["course"]) if row["course"] else None,
            "heading": float(row["heading"]) if row["heading"] else None,
            "destination": row["destination"],
            "eta": row["eta"].isoformat() if row["eta"] else None,
            "draught": float(row["draught"]) if row["draught"] else None,
            "flag_country": row["flag_country"],
            "cargo_type": row["cargo_type"],
            "time": row["time"].isoformat(),
        }
    }


@router.get("/{mmsi}/trail")
async def get_vessel_trail(
    mmsi: int,
    hours: int = Query(24, le=168),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Get vessel trail (position history) for map animation.

    Returns positions sorted chronologically (oldest first).
    Max 168 hours (7 days). Capped at 1000 points.
    """
    result = await db.execute(
        text("""
            SELECT mmsi, latitude, longitude, speed_knots, course, time
            FROM vessel_positions
            WHERE mmsi = :mmsi AND time > NOW() - make_interval(hours => :hours)
            ORDER BY time ASC
            LIMIT 1000
        """),
        {"mmsi": mmsi, "hours": hours},
    )
    rows = result.mappings().all()

    return {
        "data": [
            {
                "mmsi": row["mmsi"],
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "speed_knots": float(row["speed_knots"]) if row["speed_knots"] else None,
                "course": float(row["course"]) if row["course"] else None,
                "time": row["time"].isoformat(),
            }
            for row in rows
        ]
    }
