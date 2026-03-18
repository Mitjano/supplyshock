"""ETA calculator for active voyages.

Uses haversine great-circle distance and rolling average speed
from recent vessel positions to estimate arrival time.
"""

import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in nautical miles."""
    R_NM = 3440.065  # Earth radius in nautical miles

    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    return R_NM * c


async def calculate_eta(db: AsyncSession, voyage_id: str) -> dict:
    """Calculate ETA for an active voyage.

    Steps:
        1. Get voyage's MMSI and destination port
        2. Fetch latest vessel position
        3. Fetch destination port coordinates
        4. Calculate great-circle distance (haversine)
        5. Get average speed from last 6 hours of positions
        6. ETA = remaining_distance / avg_speed

    Returns:
        {
            "eta_utc": str | None,
            "remaining_distance_nm": float,
            "avg_speed_knots": float,
            "confidence": str,  # "high", "medium", "low"
        }
    """
    # 1. Get voyage info
    voyage_result = await db.execute(
        text("""
            SELECT v.mmsi, v.dest_port_id,
                   dp.latitude AS dest_lat, dp.longitude AS dest_lon
            FROM voyages v
            LEFT JOIN ports dp ON dp.id = v.dest_port_id
            WHERE v.id = :voyage_id
        """),
        {"voyage_id": voyage_id},
    )
    voyage = voyage_result.mappings().first()
    if not voyage or not voyage["mmsi"] or not voyage["dest_port_id"]:
        return {
            "eta_utc": None,
            "remaining_distance_nm": 0.0,
            "avg_speed_knots": 0.0,
            "confidence": "low",
        }

    mmsi = voyage["mmsi"]
    dest_lat = float(voyage["dest_lat"])
    dest_lon = float(voyage["dest_lon"])

    # 2. Get latest vessel position
    pos_result = await db.execute(
        text("""
            SELECT latitude, longitude
            FROM vessel_positions
            WHERE mmsi = :mmsi
            ORDER BY time DESC
            LIMIT 1
        """),
        {"mmsi": mmsi},
    )
    pos = pos_result.mappings().first()
    if not pos:
        return {
            "eta_utc": None,
            "remaining_distance_nm": 0.0,
            "avg_speed_knots": 0.0,
            "confidence": "low",
        }

    vessel_lat = float(pos["latitude"])
    vessel_lon = float(pos["longitude"])

    # 3. Calculate remaining distance
    remaining_distance_nm = _haversine_nm(vessel_lat, vessel_lon, dest_lat, dest_lon)

    # 4. Get average speed from last 6 hours and count data points
    speed_result = await db.execute(
        text("""
            SELECT AVG(speed_knots) AS avg_speed,
                   COUNT(*) AS point_count
            FROM vessel_positions
            WHERE mmsi = :mmsi
              AND time > NOW() - INTERVAL '6 hours'
              AND speed_knots > 0.5
        """),
        {"mmsi": mmsi},
    )
    speed_row = speed_result.mappings().first()

    avg_speed = float(speed_row["avg_speed"]) if speed_row and speed_row["avg_speed"] else 0.0
    point_count = speed_row["point_count"] if speed_row else 0

    # 5. Determine confidence based on data points in last 6h
    if point_count > 3:
        confidence = "high"
    elif point_count >= 1:
        confidence = "medium"
    else:
        confidence = "low"

    # 6. Calculate ETA
    eta_utc = None
    if avg_speed > 0.5:
        hours_remaining = remaining_distance_nm / avg_speed
        eta_dt = datetime.now(timezone.utc) + timedelta(hours=hours_remaining)
        eta_utc = eta_dt.isoformat()

    return {
        "eta_utc": eta_utc,
        "remaining_distance_nm": round(remaining_distance_nm, 1),
        "avg_speed_knots": round(avg_speed, 1),
        "confidence": confidence,
    }
