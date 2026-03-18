"""Port congestion analytics.

Calculates real-time congestion metrics for ports based on
vessel positions within port geofences.
"""

import json
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("supplyshock.analytics.port_congestion")

# Geofence default radius in nautical miles (≈ 9.26 km)
DEFAULT_GEOFENCE_RADIUS_NM = 5.0

# 1 nautical mile ≈ 1.852 km; 1 degree latitude ≈ 60 nm
NM_TO_DEGREES = 1.0 / 60.0


async def calculate_port_congestion(db: AsyncSession, port_id: str) -> dict:
    """Calculate real-time congestion for a single port.

    Counts vessels with speed < 1 knot within the port's geofence radius
    (waiting/anchored vessels) and produces a congestion index.

    Returns:
        {
            "congestion_index": int,    # 0-100
            "waiting_vessels": int,
            "risk_level": str,          # "normal", "elevated", "high", "critical"
        }
    """
    # Get port location and geofence radius
    port_result = await db.execute(
        text("""
            SELECT latitude, longitude, radius_km
            FROM ports
            WHERE id = :port_id
        """),
        {"port_id": port_id},
    )
    port = port_result.mappings().first()
    if not port:
        return {"congestion_index": 0, "waiting_vessels": 0, "risk_level": "normal"}

    port_lat = float(port["latitude"])
    port_lon = float(port["longitude"])
    # Convert radius_km to nautical miles; fall back to default 5nm
    radius_nm = (float(port["radius_km"]) / 1.852) if port["radius_km"] else DEFAULT_GEOFENCE_RADIUS_NM

    # Approximate bounding box in degrees
    lat_delta = radius_nm * NM_TO_DEGREES
    # Longitude degrees vary by latitude
    lon_delta = radius_nm * NM_TO_DEGREES / max(0.1, abs(__import__("math").cos(__import__("math").radians(port_lat))))

    # Count vessels with speed < 1 knot (waiting/anchored) within geofence
    result = await db.execute(
        text("""
            SELECT COUNT(DISTINCT vp.mmsi) AS waiting_vessels
            FROM vessel_positions vp
            WHERE vp.time > NOW() - INTERVAL '2 hours'
              AND vp.speed_knots < 1.0
              AND vp.latitude BETWEEN :min_lat AND :max_lat
              AND vp.longitude BETWEEN :min_lon AND :max_lon
        """),
        {
            "min_lat": port_lat - lat_delta,
            "max_lat": port_lat + lat_delta,
            "min_lon": port_lon - lon_delta,
            "max_lon": port_lon + lon_delta,
        },
    )
    row = result.mappings().first()
    waiting_vessels = row["waiting_vessels"] if row else 0

    # Congestion index: 0-100, capped
    congestion_index = min(waiting_vessels * 5, 100)

    # Risk level thresholds
    if congestion_index > 80:
        risk_level = "critical"
    elif congestion_index > 60:
        risk_level = "high"
    elif congestion_index >= 30:
        risk_level = "elevated"
    else:
        risk_level = "normal"

    return {
        "congestion_index": congestion_index,
        "waiting_vessels": waiting_vessels,
        "risk_level": risk_level,
    }


async def update_all_port_congestion(db: AsyncSession) -> int:
    """Batch-update congestion for all major ports — stores in Redis cache.

    Intended to be called by Celery Beat every 15 minutes.
    Each result is cached at `port:{port_id}:congestion` with 20 min TTL.

    Returns:
        Number of ports updated.
    """
    from dependencies import get_redis

    redis = await get_redis()

    # Fetch all major ports
    result = await db.execute(
        text("SELECT id FROM ports WHERE is_major = TRUE ORDER BY name"),
    )
    port_ids = [str(row["id"]) for row in result.mappings().all()]

    updated = 0
    for port_id in port_ids:
        try:
            congestion = await calculate_port_congestion(db, port_id)
            cache_key = f"port:{port_id}:congestion"
            await redis.setex(cache_key, 1200, json.dumps(congestion))  # 20 min TTL
            updated += 1
        except Exception:
            logger.exception("Failed to update congestion for port %s", port_id)

    logger.info("Updated congestion for %d / %d major ports", updated, len(port_ids))
    return updated
