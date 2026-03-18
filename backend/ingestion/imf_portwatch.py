"""IMF PortWatch chokepoint transit data ingestion (Issue #76).

Fetches chokepoint transit counts and port-level trade volumes from the
IMF PortWatch API (free, no key required).

Celery Beat: every 6 hours.
"""

import logging
from datetime import datetime, timezone, timedelta

import psycopg2
import requests

from config import settings

logger = logging.getLogger("imf_portwatch")

PORTWATCH_BASE = "https://portwatch.imf.org/api/"

# Major chokepoints tracked by PortWatch
CHOKEPOINTS = {
    "suez": {"name": "Suez Canal", "node_id": "suez"},
    "panama": {"name": "Panama Canal", "node_id": "panama"},
    "hormuz": {"name": "Strait of Hormuz", "node_id": "hormuz"},
    "malacca": {"name": "Strait of Malacca", "node_id": "malacca"},
    "bosporus": {"name": "Turkish Straits", "node_id": "bosporus"},
    "gibraltar": {"name": "Strait of Gibraltar", "node_id": "gibraltar"},
    "dover": {"name": "Strait of Dover", "node_id": "dover"},
    "cape": {"name": "Cape of Good Hope", "node_id": "cape"},
}


def _ensure_table(conn):
    """Create chokepoint_transits table if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chokepoint_transits (
                id BIGSERIAL PRIMARY KEY,
                node_id TEXT NOT NULL,
                transit_date DATE NOT NULL,
                vessel_count INTEGER DEFAULT 0,
                total_teu DOUBLE PRECISION DEFAULT 0,
                total_tonnes DOUBLE PRECISION DEFAULT 0,
                avg_wait_hours DOUBLE PRECISION,
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (node_id, transit_date)
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_chokepoint_transits_node_date
            ON chokepoint_transits (node_id, transit_date DESC)
        """)
    conn.commit()


def _fetch_portwatch_data(chokepoint_id: str, days: int = 30) -> list[dict]:
    """Fetch transit data for a chokepoint from IMF PortWatch API."""
    results = []
    try:
        # PortWatch exposes chokepoint trade flow data via ArcGIS Feature Service
        url = f"{PORTWATCH_BASE}trade/chokepoint/{chokepoint_id}"
        params = {
            "days": days,
            "f": "json",
        }
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            features = data.get("features", data.get("data", []))
            for feat in features:
                attrs = feat.get("attributes", feat) if isinstance(feat, dict) else {}
                results.append({
                    "transit_date": attrs.get("date", attrs.get("transit_date")),
                    "vessel_count": attrs.get("vessel_count", attrs.get("n_vessels", 0)),
                    "total_teu": attrs.get("total_teu", 0),
                    "total_tonnes": attrs.get("total_tonnes", attrs.get("trade_value", 0)),
                })
        else:
            logger.warning("PortWatch API returned %d for %s", resp.status_code, chokepoint_id)
    except Exception as e:
        logger.error("Failed to fetch PortWatch data for %s: %s", chokepoint_id, e)

    # Fallback: try the PortWatch FeatureServer endpoint
    if not results:
        try:
            fs_url = (
                "https://services.arcgis.com/ue9rwulIoeLEI9bj/ArcGIS/rest/services/"
                "portwatch_chokepoint/FeatureServer/0/query"
            )
            params = {
                "where": f"chokepoint='{chokepoint_id}'",
                "outFields": "*",
                "orderByFields": "date DESC",
                "resultRecordCount": days,
                "f": "json",
            }
            resp = requests.get(fs_url, params=params, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                for feat in data.get("features", []):
                    attrs = feat.get("attributes", {})
                    date_val = attrs.get("date")
                    if isinstance(date_val, (int, float)):
                        date_val = datetime.fromtimestamp(
                            date_val / 1000, tz=timezone.utc
                        ).strftime("%Y-%m-%d")
                    results.append({
                        "transit_date": date_val,
                        "vessel_count": attrs.get("n_vessels", 0),
                        "total_teu": attrs.get("teu", 0),
                        "total_tonnes": attrs.get("tonnes", 0),
                    })
        except Exception as e:
            logger.error("PortWatch FeatureServer fallback failed for %s: %s", chokepoint_id, e)

    return results


def ingest_imf_portwatch():
    """Ingest chokepoint transit data from IMF PortWatch."""
    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        _ensure_table(conn)
        total = 0

        for cp_id, cp_info in CHOKEPOINTS.items():
            records = _fetch_portwatch_data(cp_id)
            if not records:
                continue

            with conn.cursor() as cur:
                for rec in records:
                    transit_date = rec.get("transit_date")
                    if not transit_date:
                        continue
                    try:
                        cur.execute("""
                            INSERT INTO chokepoint_transits
                                (node_id, transit_date, vessel_count, total_teu, total_tonnes)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (node_id, transit_date)
                            DO UPDATE SET
                                vessel_count = EXCLUDED.vessel_count,
                                total_teu = EXCLUDED.total_teu,
                                total_tonnes = EXCLUDED.total_tonnes
                        """, (
                            cp_info["node_id"],
                            transit_date,
                            rec.get("vessel_count", 0),
                            rec.get("total_teu", 0),
                            rec.get("total_tonnes", 0),
                        ))
                        total += 1
                    except Exception as e:
                        logger.warning("Failed to upsert transit for %s/%s: %s", cp_id, transit_date, e)
                        conn.rollback()
                        continue

            conn.commit()
            logger.info("Ingested %d transit records for %s", len(records), cp_id)

        logger.info("IMF PortWatch ingestion complete: %d total records", total)
        return {"records_ingested": total}
    finally:
        conn.close()
