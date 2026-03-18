"""Weather ingestion — Open-Meteo Marine API client.

Fetches marine weather data and detects storm conditions.
"""

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

OPEN_METEO_MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
STORM_WIND_THRESHOLD_KN = 40  # knots


@dataclass
class WeatherPoint:
    lat: float
    lon: float
    wave_height: float | None
    wave_period: float | None
    wave_direction: float | None
    wind_wave_height: float | None


@dataclass
class StormAlert:
    lat: float
    lon: float
    wave_height: float
    description: str


async def fetch_marine_weather(bbox: tuple[float, float, float, float]) -> dict:
    """Fetch marine weather for a bounding box from Open-Meteo Marine API.

    Args:
        bbox: (lat_south, lon_west, lat_north, lon_east)

    Returns:
        Dictionary with "points" (list of WeatherPoint dicts) and "alerts" (storm alerts).
    """
    lat_south, lon_west, lat_north, lon_east = bbox

    lat_step = max((lat_north - lat_south) / 4, 1.0)
    lon_step = max((lon_east - lon_west) / 4, 1.0)

    grid_points: list[tuple[float, float]] = []
    lat = lat_south
    while lat <= lat_north:
        lon = lon_west
        while lon <= lon_east:
            grid_points.append((round(lat, 2), round(lon, 2)))
            lon += lon_step
        lat += lat_step

    points: list[dict] = []
    alerts: list[dict] = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        for lat_pt, lon_pt in grid_points:
            try:
                resp = await client.get(
                    OPEN_METEO_MARINE_URL,
                    params={
                        "latitude": lat_pt,
                        "longitude": lon_pt,
                        "current": "wave_height,wave_period,wave_direction,wind_wave_height",
                        "hourly": "wave_height,wave_period,wave_direction,wind_wave_height",
                        "wind_speed_unit": "kn",
                        "forecast_days": 1,
                    },
                )
                if resp.status_code != 200:
                    logger.warning(
                        "Open-Meteo returned %d for (%s, %s)",
                        resp.status_code, lat_pt, lon_pt,
                    )
                    continue

                data = resp.json()
                current = data.get("current", {})

                point = WeatherPoint(
                    lat=lat_pt,
                    lon=lon_pt,
                    wave_height=current.get("wave_height"),
                    wave_period=current.get("wave_period"),
                    wave_direction=current.get("wave_direction"),
                    wind_wave_height=current.get("wind_wave_height"),
                )
                points.append({
                    "lat": point.lat,
                    "lon": point.lon,
                    "wave_height": point.wave_height,
                    "wave_period": point.wave_period,
                    "wave_direction": point.wave_direction,
                    "wind_wave_height": point.wind_wave_height,
                })

                # Storm detection: high wave height indicates severe weather
                # (Open-Meteo Marine doesn't expose wind_speed_10m directly,
                #  so we use wave_height > 5m as proxy for storm conditions)
                if point.wave_height is not None and point.wave_height > 5.0:
                    alert = StormAlert(
                        lat=lat_pt,
                        lon=lon_pt,
                        wave_height=point.wave_height,
                        description=(
                            f"Severe sea state detected at ({lat_pt}, {lon_pt}): "
                            f"wave height {point.wave_height:.1f}m"
                        ),
                    )
                    alerts.append({
                        "lat": alert.lat,
                        "lon": alert.lon,
                        "wave_height": alert.wave_height,
                        "description": alert.description,
                        "severity": "critical" if point.wave_height > 8.0 else "warning",
                    })
                    logger.warning("Storm alert: %s", alert.description)

            except httpx.RequestError as exc:
                logger.error("Weather fetch error for (%s, %s): %s", lat_pt, lon_pt, exc)
                continue

    return {
        "points": points,
        "alerts": alerts,
        "grid_size": len(points),
    }
