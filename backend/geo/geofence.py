"""Port geofencing utilities — wraps PostGIS is_in_port() function.

Usage:
    from geo.geofence import check_port, get_vessels_in_port

    # Check if a coordinate is inside any port's geofence
    result = await check_port(session, lat=51.95, lon=1.35)
    # → {"port_id": "uuid", "port_name": "Felixstowe", "distance_km": 1.2} or None

    # Get all vessels currently inside a port
    vessels = await get_vessels_in_port(session, port_id="uuid")
"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def check_port(
    session: AsyncSession,
    lat: float,
    lon: float,
) -> dict[str, Any] | None:
    """Check if coordinates fall within any port's geofence radius.

    Uses PostGIS ST_DWithin for accurate spherical distance calculation.
    Returns the closest port if within radius, None otherwise.
    """
    result = await session.execute(
        text("SELECT port_id, port_name, distance_km FROM is_in_port(:lat, :lon)"),
        {"lat": lat, "lon": lon},
    )
    row = result.mappings().first()
    if not row:
        return None
    return {
        "port_id": str(row["port_id"]),
        "port_name": row["port_name"],
        "distance_km": round(row["distance_km"], 2),
    }


async def get_vessels_in_port(
    session: AsyncSession,
    port_id: str,
) -> list[dict[str, Any]]:
    """Get all vessels currently within a port's geofence radius.

    Uses the latest_vessel_positions materialized view for performance.
    """
    result = await session.execute(
        text("SELECT * FROM vessels_in_port(:port_id)"),
        {"port_id": port_id},
    )
    rows = result.mappings().all()
    return [
        {
            "mmsi": row["mmsi"],
            "vessel_name": row["vessel_name"],
            "vessel_type": row["vessel_type"],
            "distance_km": round(row["distance_km"], 2),
            "speed_knots": float(row["speed_knots"]) if row["speed_knots"] else None,
            "last_seen": row["last_seen"].isoformat(),
        }
        for row in rows
    ]


async def get_nearby_ports(
    session: AsyncSession,
    lat: float,
    lon: float,
    radius_km: float = 50.0,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Find ports within a given radius of coordinates.

    Unlike check_port() which uses each port's own radius_km,
    this uses a fixed search radius for discovery/UI purposes.
    """
    result = await session.execute(
        text("""
            SELECT
                p.id, p.name, p.country_code, p.latitude, p.longitude,
                p.commodities, p.is_major, p.radius_km,
                ST_Distance(
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    ST_SetSRID(ST_MakePoint(p.longitude, p.latitude), 4326)::geography
                ) / 1000.0 AS distance_km
            FROM ports p
            WHERE ST_DWithin(
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                ST_SetSRID(ST_MakePoint(p.longitude, p.latitude), 4326)::geography,
                :radius_m
            )
            ORDER BY distance_km ASC
            LIMIT :limit
        """),
        {"lat": lat, "lon": lon, "radius_m": radius_km * 1000, "limit": limit},
    )
    rows = result.mappings().all()
    return [
        {
            "id": str(row["id"]),
            "name": row["name"],
            "country_code": row["country_code"],
            "latitude": float(row["latitude"]),
            "longitude": float(row["longitude"]),
            "commodities": row["commodities"] or [],
            "is_major": row["is_major"],
            "radius_km": float(row["radius_km"]) if row["radius_km"] else 5.0,
            "distance_km": round(row["distance_km"], 2),
        }
        for row in rows
    ]
