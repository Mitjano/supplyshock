"""GDELT-based conflict event ingestion (Issue #79).

Uses GDELT GKG (Global Knowledge Graph) as free alternative to ACLED
(which requires commercial license). Filters for conflict/violence themes
near critical infrastructure.

Celery Beat: daily.
"""

import logging
from datetime import datetime, timezone, timedelta
from io import StringIO

import psycopg2
import requests

from config import settings

logger = logging.getLogger("acled_gdelt")

GDELT_GKG_BASE = "http://data.gdeltproject.org/gdeltv2"
GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

# Regions and their bounding boxes (lat_min, lat_max, lon_min, lon_max)
REGIONS = {
    "middle_east": {"bbox": (12, 42, 25, 63), "name": "Middle East"},
    "east_asia": {"bbox": (18, 54, 73, 145), "name": "East Asia"},
    "europe": {"bbox": (35, 72, -25, 45), "name": "Europe"},
    "africa_horn": {"bbox": (-5, 20, 30, 55), "name": "Horn of Africa"},
    "south_asia": {"bbox": (5, 37, 60, 100), "name": "South Asia"},
    "southeast_asia": {"bbox": (-11, 20, 95, 141), "name": "Southeast Asia"},
    "black_sea": {"bbox": (40, 48, 27, 42), "name": "Black Sea Region"},
}

# GDELT themes related to conflict near infrastructure
CONFLICT_THEMES = [
    "TERROR", "KILL", "MILITARY", "BLOCKADE", "PROTEST",
    "SEIZE", "WOUND", "THREAT", "ARMEDCONFLICT", "REBELLION",
]

INFRASTRUCTURE_THEMES = [
    "PIPELINE", "PORT", "SHIPPING", "OIL", "GAS", "ENERGY",
    "REFINERY", "STRAIT", "CANAL", "MARITIME",
]


def _ensure_table(conn):
    """Create conflict_events table if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS conflict_events (
                id BIGSERIAL PRIMARY KEY,
                event_date DATE NOT NULL,
                region TEXT NOT NULL,
                latitude DOUBLE PRECISION,
                longitude DOUBLE PRECISION,
                event_type TEXT NOT NULL,
                severity TEXT DEFAULT 'medium',
                title TEXT,
                source_url TEXT,
                source TEXT NOT NULL DEFAULT 'gdelt',
                themes TEXT[],
                goldstein_scale DOUBLE PRECISION,
                num_mentions INTEGER DEFAULT 1,
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_conflict_events_region_date
            ON conflict_events (region, event_date DESC)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_conflict_events_date
            ON conflict_events (event_date DESC)
        """)
    conn.commit()


def _classify_region(lat: float, lon: float) -> str | None:
    """Classify a coordinate into a predefined region."""
    for region_id, info in REGIONS.items():
        bbox = info["bbox"]
        if bbox[0] <= lat <= bbox[1] and bbox[2] <= lon <= bbox[3]:
            return region_id
    return None


def _classify_severity(goldstein: float, mentions: int) -> str:
    """Classify event severity from Goldstein scale and mention count."""
    if goldstein is not None and goldstein < -7:
        return "critical"
    if goldstein is not None and goldstein < -4:
        if mentions >= 10:
            return "high"
        return "medium"
    if mentions >= 20:
        return "high"
    if mentions >= 5:
        return "medium"
    return "low"


def _fetch_gdelt_events() -> list[dict]:
    """Fetch recent conflict events near infrastructure from GDELT Doc API."""
    results = []

    # Build query for conflict + infrastructure themes
    conflict_query = " OR ".join(CONFLICT_THEMES[:5])
    infra_query = " OR ".join(INFRASTRUCTURE_THEMES[:5])
    query = f"({conflict_query}) ({infra_query})"

    try:
        params = {
            "query": query,
            "mode": "ArtList",
            "maxrecords": 250,
            "format": "json",
            "timespan": "24h",
        }
        resp = requests.get(GDELT_DOC_API, params=params, timeout=60)
        if resp.status_code != 200:
            logger.warning("GDELT Doc API returned %d", resp.status_code)
            return results

        data = resp.json()
        articles = data.get("articles", [])

        for art in articles:
            lat = art.get("sourcecountylat")
            lon = art.get("sourcecountylong")

            if lat is None or lon is None:
                # Try seendate geolocation
                lat = art.get("lat")
                lon = art.get("long")

            if lat is None or lon is None:
                continue

            try:
                lat = float(lat)
                lon = float(lon)
            except (ValueError, TypeError):
                continue

            region = _classify_region(lat, lon)
            if region is None:
                continue

            # Extract themes
            title = art.get("title", "")
            url = art.get("url", "")
            date_str = art.get("seendate", "")
            goldstein = art.get("goldstein")

            # Determine event type
            title_lower = title.lower()
            if any(t.lower() in title_lower for t in ["attack", "strike", "bomb", "kill"]):
                event_type = "armed_conflict"
            elif any(t.lower() in title_lower for t in ["blockade", "seize", "sanction"]):
                event_type = "blockade"
            elif any(t.lower() in title_lower for t in ["protest", "demonstration"]):
                event_type = "protest"
            elif any(t.lower() in title_lower for t in ["military", "deploy", "naval"]):
                event_type = "military_activity"
            else:
                event_type = "conflict_related"

            try:
                event_date = datetime.strptime(date_str[:8], "%Y%m%d").date() if date_str else datetime.now(timezone.utc).date()
            except ValueError:
                event_date = datetime.now(timezone.utc).date()

            severity = _classify_severity(
                float(goldstein) if goldstein else None,
                art.get("nummentions", 1) or 1,
            )

            results.append({
                "event_date": event_date,
                "region": region,
                "latitude": lat,
                "longitude": lon,
                "event_type": event_type,
                "severity": severity,
                "title": title[:500],
                "source_url": url[:1000],
                "goldstein_scale": float(goldstein) if goldstein else None,
                "num_mentions": art.get("nummentions", 1) or 1,
            })

    except Exception as e:
        logger.error("Failed to fetch GDELT events: %s", e)

    return results


def ingest_conflict_events():
    """Ingest conflict events from GDELT."""
    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        _ensure_table(conn)

        events = _fetch_gdelt_events()
        if not events:
            logger.info("No conflict events found")
            return {"records_ingested": 0}

        total = 0
        with conn.cursor() as cur:
            for evt in events:
                try:
                    cur.execute("""
                        INSERT INTO conflict_events
                            (event_date, region, latitude, longitude, event_type,
                             severity, title, source_url, source,
                             goldstein_scale, num_mentions)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'gdelt', %s, %s)
                    """, (
                        evt["event_date"],
                        evt["region"],
                        evt["latitude"],
                        evt["longitude"],
                        evt["event_type"],
                        evt["severity"],
                        evt["title"],
                        evt["source_url"],
                        evt["goldstein_scale"],
                        evt["num_mentions"],
                    ))
                    total += 1
                except Exception as e:
                    logger.warning("Failed to insert conflict event: %s", e)
                    conn.rollback()
                    continue

        conn.commit()
        logger.info("GDELT conflict ingestion complete: %d events", total)
        return {"records_ingested": total}
    finally:
        conn.close()
