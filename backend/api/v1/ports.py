"""Port endpoints — /api/v1/ports/*

- GET /ports                   — list/filter ports (bbox, major, commodity)
- GET /ports/{id}              — port detail
- GET /ports/{id}/vessels      — vessels currently in port geofence
- GET /ports/{id}/congestion   — port congestion metrics
- GET /ports/{id}/analytics    — port performance analytics (Issue #72)
- GET /ports/ranking           — port ranking by congestion/throughput (Issue #72)
"""

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from analytics.port_congestion import calculate_port_congestion
from dependencies import get_db, get_redis
from geo.geofence import get_vessels_in_port
from middleware.auth import require_auth
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/ports", tags=["Ports"])


@router.get("")
async def list_ports(
    bbox: str | None = Query(None, description="min_lng,min_lat,max_lng,max_lat"),
    is_major: bool | None = Query(None),
    commodity: str | None = Query(None, description="Filter by commodity in commodities array"),
    offset: int = Query(0, ge=0),
    limit: int = Query(500, le=5000),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """List ports with optional filters."""
    conditions = []
    params: dict[str, Any] = {"limit": limit}

    if bbox:
        parts = bbox.split(",")
        if len(parts) != 4:
            raise HTTPException(status_code=400, detail={"error": "Invalid bbox format", "code": "INVALID_BBOX"})
        try:
            min_lng, min_lat, max_lng, max_lat = [float(p) for p in parts]
            conditions.append("latitude BETWEEN :min_lat AND :max_lat")
            conditions.append("longitude BETWEEN :min_lng AND :max_lng")
            params.update(min_lat=min_lat, max_lat=max_lat, min_lng=min_lng, max_lng=max_lng)
        except ValueError:
            raise HTTPException(status_code=400, detail={"error": "Invalid bbox values", "code": "INVALID_BBOX"})

    if is_major is not None:
        conditions.append("is_major = :is_major")
        params["is_major"] = is_major

    if commodity:
        conditions.append(":commodity = ANY(commodities)")
        params["commodity"] = commodity

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    params["offset"] = offset

    # Get total count
    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM ports {where}"),
        params,
    )
    total = count_result.scalar()

    result = await db.execute(
        text(f"""
            SELECT id, wpi_number, name, country_code, latitude, longitude,
                   region, harbor_type, commodities, annual_throughput_mt,
                   radius_km, is_major, is_chokepoint
            FROM ports
            {where}
            ORDER BY is_major DESC, name ASC
            LIMIT :limit OFFSET :offset
        """),
        params,
    )
    rows = result.mappings().all()

    return {
        "data": [
            {
                "id": str(row["id"]),
                "wpi_number": row["wpi_number"],
                "name": row["name"],
                "country_code": row["country_code"],
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "region": row["region"],
                "harbor_type": row["harbor_type"],
                "commodities": row["commodities"] or [],
                "annual_throughput_mt": float(row["annual_throughput_mt"]) if row["annual_throughput_mt"] else None,
                "radius_km": float(row["radius_km"]) if row["radius_km"] else 5.0,
                "is_major": row["is_major"],
                "is_chokepoint": row["is_chokepoint"],
            }
            for row in rows
        ],
        "meta": {"total": total, "offset": offset, "limit": limit},
    }


# ── Issue #72 — Port Ranking (must be before /{port_id} to avoid path collision) ──

@router.get("/ranking")
async def get_port_ranking(
    by: str = Query("congestion", description="Rank by: congestion, throughput, dwell_time"),
    limit: int = Query(20, le=100),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Rank ports by congestion, throughput, or dwell time."""
    result = await db.execute(
        text("""
            SELECT DISTINCT ON (pa.port_id)
                pa.port_id, p.name, p.country_code, p.region,
                pa.dwell_time_median_hours, pa.turnaround_hours,
                pa.queue_length, pa.throughput_vessels, pa.vessel_count,
                pa.avg_wait_hours, pa.calculated_at
            FROM port_analytics pa
            JOIN ports p ON pa.port_id = p.id
            ORDER BY pa.port_id, pa.calculated_at DESC
        """),
    )
    rows = result.mappings().all()

    # Sort in Python since DISTINCT ON prevents direct ORDER BY on analytics columns
    sort_key_map = {
        "congestion": lambda r: r["queue_length"] or 0,
        "throughput": lambda r: r["throughput_vessels"] or 0,
        "dwell_time": lambda r: r["dwell_time_median_hours"] or 0,
    }
    sort_fn = sort_key_map.get(by, sort_key_map["congestion"])
    sorted_rows = sorted(rows, key=sort_fn, reverse=True)[:limit]

    return {
        "data": [
            {
                "port_id": str(r["port_id"]),
                "name": r["name"],
                "country_code": r["country_code"],
                "region": r["region"],
                "dwell_time_median_hours": float(r["dwell_time_median_hours"]) if r["dwell_time_median_hours"] else None,
                "turnaround_hours": float(r["turnaround_hours"]) if r["turnaround_hours"] else None,
                "queue_length": r["queue_length"],
                "throughput_vessels": r["throughput_vessels"],
                "vessel_count": r["vessel_count"],
                "avg_wait_hours": float(r["avg_wait_hours"]) if r["avg_wait_hours"] else None,
                "calculated_at": r["calculated_at"].isoformat() if hasattr(r["calculated_at"], "isoformat") else str(r["calculated_at"]),
            }
            for r in sorted_rows
        ],
        "meta": {"ranked_by": by, "limit": limit},
    }


@router.get("/{port_id}")
async def get_port(
    port_id: str,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Get port detail by ID."""
    result = await db.execute(
        text("""
            SELECT id, wpi_number, name, country_code, latitude, longitude,
                   region, harbor_type, max_vessel_size, commodities,
                   annual_throughput_mt, radius_km, unlocode, is_major, is_chokepoint
            FROM ports WHERE id = :port_id
        """),
        {"port_id": port_id},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Port not found")

    return {
        "id": str(row["id"]),
        "wpi_number": row["wpi_number"],
        "name": row["name"],
        "country_code": row["country_code"],
        "latitude": float(row["latitude"]),
        "longitude": float(row["longitude"]),
        "region": row["region"],
        "harbor_type": row["harbor_type"],
        "max_vessel_size": row["max_vessel_size"],
        "commodities": row["commodities"] or [],
        "annual_throughput_mt": float(row["annual_throughput_mt"]) if row["annual_throughput_mt"] else None,
        "radius_km": float(row["radius_km"]) if row["radius_km"] else 5.0,
        "unlocode": row["unlocode"],
        "is_major": row["is_major"],
        "is_chokepoint": row["is_chokepoint"],
    }


@router.get("/{port_id}/vessels")
async def list_vessels_in_port(
    port_id: str,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Get vessels currently within a port's geofence radius.

    Uses PostGIS ST_DWithin against latest_vessel_positions.
    """
    # Verify port exists
    port_check = await db.execute(
        text("SELECT id, name FROM ports WHERE id = :port_id"),
        {"port_id": port_id},
    )
    if not port_check.mappings().first():
        raise HTTPException(status_code=404, detail="Port not found")

    vessels = await get_vessels_in_port(db, port_id)

    return {
        "data": vessels,
        "meta": {"port_id": port_id, "vessel_count": len(vessels)},
    }


@router.get("/{port_id}/congestion")
async def get_port_congestion(
    port_id: str,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Get real-time congestion metrics for a port.

    Returns cached data when available (refreshed every 15 min),
    otherwise computes on-the-fly.
    """
    # Verify port exists
    port_check = await db.execute(
        text("SELECT id, name FROM ports WHERE id = :port_id"),
        {"port_id": port_id},
    )
    port = port_check.mappings().first()
    if not port:
        raise HTTPException(status_code=404, detail="Port not found")

    # Try Redis cache first
    try:
        redis = await get_redis()
        cached = await redis.get(f"port:{port_id}:congestion")
        if cached:
            data = json.loads(cached)
            data["source"] = "cache"
            return {"data": data, "meta": {"port_id": port_id, "port_name": port["name"]}}
    except Exception:
        pass

    # Compute on-the-fly
    data = await calculate_port_congestion(db, port_id)
    data["source"] = "live"
    return {"data": data, "meta": {"port_id": port_id, "port_name": port["name"]}}


# ── Issue #72 — Port Analytics ──

@router.get("/{port_id}/analytics")
async def get_port_analytics(
    port_id: str,
    period: str = Query("30d", description="Period: 7d, 30d, 90d"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Get performance analytics for a specific port."""
    # Verify port exists
    port_check = await db.execute(
        text("SELECT id, name FROM ports WHERE id = :port_id"),
        {"port_id": port_id},
    )
    port = port_check.mappings().first()
    if not port:
        raise HTTPException(status_code=404, detail="Port not found")

    interval_map = {"7d": "7 days", "30d": "30 days", "90d": "90 days"}
    interval = interval_map.get(period, "30 days")

    result = await db.execute(
        text(f"""
            SELECT dwell_time_median_hours, turnaround_hours,
                   queue_length, throughput_vessels, vessel_count,
                   avg_wait_hours, period_start, calculated_at
            FROM port_analytics
            WHERE port_id = :port_id
              AND period_start >= NOW() - INTERVAL '{interval}'
            ORDER BY period_start DESC
        """),
        {"port_id": port_id},
    )
    rows = result.mappings().all()

    if not rows:
        return {
            "data": None,
            "meta": {"port_id": port_id, "port_name": port["name"], "period": period},
            "message": "No analytics data available for this period",
        }

    # Latest snapshot
    latest = rows[0]

    # Historical trend
    history = [
        {
            "date": r["period_start"].isoformat() if hasattr(r["period_start"], "isoformat") else str(r["period_start"]),
            "dwell_time_median_hours": float(r["dwell_time_median_hours"]) if r["dwell_time_median_hours"] else None,
            "queue_length": r["queue_length"],
            "throughput_vessels": r["throughput_vessels"],
            "vessel_count": r["vessel_count"],
        }
        for r in rows
    ]

    return {
        "data": {
            "dwell_time_median_hours": float(latest["dwell_time_median_hours"]) if latest["dwell_time_median_hours"] else None,
            "turnaround_hours": float(latest["turnaround_hours"]) if latest["turnaround_hours"] else None,
            "queue_length": latest["queue_length"],
            "throughput_vessels": latest["throughput_vessels"],
            "vessel_count": latest["vessel_count"],
            "avg_wait_hours": float(latest["avg_wait_hours"]) if latest["avg_wait_hours"] else None,
            "calculated_at": latest["calculated_at"].isoformat() if hasattr(latest["calculated_at"], "isoformat") else str(latest["calculated_at"]),
        },
        "history": history,
        "meta": {"port_id": port_id, "port_name": port["name"], "period": period},
    }
