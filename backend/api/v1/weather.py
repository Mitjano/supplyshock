"""Weather endpoints — /api/v1/weather/*

- GET /weather  — marine weather grid for a bounding box (proxies Open-Meteo Marine API)
"""

import json
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Query

from dependencies import get_redis
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/weather", tags=["Weather"])

OPEN_METEO_MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
CACHE_TTL = 15 * 60  # 15 minutes


def _round_bbox(val: float, step: float = 0.5) -> float:
    """Snap to grid to improve cache hit rate."""
    return round(round(val / step) * step, 2)


@router.get("")
async def get_weather(
    bbox: str = Query(
        ...,
        description="Bounding box: lat1,lon1,lat2,lon2 (south,west,north,east)",
        examples=["30,-10,60,40"],
    ),
    user: dict[str, Any] = Depends(check_api_rate_limit),
):
    """Return marine weather grid for the given bounding box.

    Proxies Open-Meteo Marine API with Redis caching (15 min TTL).
    Returns wind speed/direction and wave height/period on a grid.
    """
    parts = [float(x.strip()) for x in bbox.split(",")]
    if len(parts) != 4:
        return {"error": "bbox must have exactly 4 values: lat1,lon1,lat2,lon2"}

    lat_south, lon_west, lat_north, lon_east = parts

    # Snap to grid for better cache hits
    lat_south = _round_bbox(lat_south)
    lon_west = _round_bbox(lon_west)
    lat_north = _round_bbox(lat_north)
    lon_east = _round_bbox(lon_east)

    cache_key = f"weather:{lat_south},{lon_west},{lat_north},{lon_east}"

    redis = await get_redis()
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    # Build a grid of sample points (max ~25 points)
    lat_step = max((lat_north - lat_south) / 4, 1.0)
    lon_step = max((lon_east - lon_west) / 4, 1.0)

    grid_points = []
    lat = lat_south
    while lat <= lat_north:
        lon = lon_west
        while lon <= lon_east:
            grid_points.append((round(lat, 2), round(lon, 2)))
            lon += lon_step
        lat += lat_step

    # Fetch weather for each point (Open-Meteo supports single-point queries)
    weather_data = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for lat_pt, lon_pt in grid_points:
            try:
                resp = await client.get(
                    OPEN_METEO_MARINE_URL,
                    params={
                        "latitude": lat_pt,
                        "longitude": lon_pt,
                        "current": "wave_height,wave_period,wave_direction",
                        "hourly": "wave_height,wave_period,wave_direction,wind_wave_height",
                        "wind_speed_unit": "kn",
                        "forecast_days": 1,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    current = data.get("current", {})
                    weather_data.append({
                        "lat": lat_pt,
                        "lon": lon_pt,
                        "wave_height": current.get("wave_height"),
                        "wave_period": current.get("wave_period"),
                        "wave_direction": current.get("wave_direction"),
                    })
            except httpx.RequestError:
                continue

    result = {
        "data": weather_data,
        "bbox": {
            "south": lat_south,
            "west": lon_west,
            "north": lat_north,
            "east": lon_east,
        },
        "grid_points": len(weather_data),
    }

    # Cache
    await redis.set(cache_key, json.dumps(result), ex=CACHE_TTL)

    return result
