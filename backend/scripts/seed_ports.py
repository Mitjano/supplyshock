"""Seed ports table from NOAA World Port Index CSV.

Usage:
    docker compose exec backend python scripts/seed_ports.py

Downloads WPI CSV from NOAA MSI, parses it, and upserts into the ports table.
Also seeds the 25 bottleneck_nodes from the hardcoded list.
"""

import csv
import io
import logging
import sys

import httpx
import psycopg2
from psycopg2.extras import execute_values

from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WPI_CSV_URL = "https://msi.nga.mil/api/publications/download?key=16694622/SFH00000/UpdatedPub150.csv"

# Major commodity ports — manually curated from WPI + industry knowledge
MAJOR_PORTS = {
    "Newcastle": {"commodities": ["coal"], "annual_mt": 160},
    "Port Hedland": {"commodities": ["iron_ore"], "annual_mt": 550},
    "Dampier": {"commodities": ["iron_ore", "lng"], "annual_mt": 180},
    "Ras Tanura": {"commodities": ["crude_oil"], "annual_mt": 300},
    "Jebel Ali": {"commodities": ["crude_oil", "lng"], "annual_mt": 80},
    "Rotterdam": {"commodities": ["crude_oil", "coal", "iron_ore"], "annual_mt": 440},
    "Singapore": {"commodities": ["crude_oil", "lng"], "annual_mt": 600},
    "Shanghai": {"commodities": ["iron_ore", "coal", "copper"], "annual_mt": 700},
    "Qingdao": {"commodities": ["iron_ore", "crude_oil"], "annual_mt": 600},
    "Richards Bay": {"commodities": ["coal"], "annual_mt": 90},
    "Houston": {"commodities": ["crude_oil", "lng"], "annual_mt": 270},
    "Fujairah": {"commodities": ["crude_oil"], "annual_mt": 100},
    "Santos": {"commodities": ["iron_ore", "crude_oil"], "annual_mt": 130},
    "Gladstone": {"commodities": ["coal", "lng"], "annual_mt": 120},
    "Hay Point": {"commodities": ["coal"], "annual_mt": 110},
}

# Bottleneck nodes to seed
BOTTLENECK_NODES = [
    ("strait_hormuz", "Strait of Hormuz", "strait", "OM", 26.56, 56.25, ["crude_oil", "lng"], 21000, 21.0, 9),
    ("strait_malacca", "Strait of Malacca", "strait", "SG", 1.43, 103.5, ["crude_oil", "lng", "coal"], 16000, 16.0, 7),
    ("suez_canal", "Suez Canal", "strait", "EG", 30.58, 32.27, ["crude_oil", "lng", "coal", "iron_ore"], 12000, 12.0, 8),
    ("panama_canal", "Panama Canal", "strait", "PA", 9.0, -79.5, ["crude_oil", "lng", "copper"], 5000, 5.0, 6),
    ("bab_el_mandeb", "Bab el-Mandeb", "strait", "DJ", 12.58, 43.33, ["crude_oil", "lng"], 6200, 6.5, 8),
    ("turkish_straits", "Turkish Straits", "strait", "TR", 41.2, 29.1, ["crude_oil", "coal"], 3000, 3.0, 6),
    ("cape_good_hope", "Cape of Good Hope", "strait", "ZA", -34.35, 18.47, ["crude_oil", "coal", "iron_ore"], 8000, 8.0, 4),
    ("port_newcastle_au", "Port of Newcastle", "port", "AU", -32.92, 151.78, ["coal"], 160, 35.0, 5),
    ("port_hedland", "Port Hedland", "port", "AU", -20.31, 118.58, ["iron_ore"], 550, 45.0, 5),
    ("ras_tanura", "Ras Tanura", "port", "SA", 26.65, 50.17, ["crude_oil"], 300, 7.0, 7),
    ("rotterdam", "Port of Rotterdam", "port", "NL", 51.9, 4.5, ["crude_oil", "coal", "iron_ore"], 440, 4.0, 3),
    ("singapore_port", "Port of Singapore", "port", "SG", 1.26, 103.84, ["crude_oil", "lng"], 600, 6.0, 4),
    ("shanghai_port", "Port of Shanghai", "port", "CN", 31.23, 121.47, ["iron_ore", "coal", "copper"], 700, 7.0, 3),
    ("richards_bay", "Richards Bay", "port", "ZA", -28.78, 32.08, ["coal"], 90, 18.0, 5),
    ("houston_port", "Port of Houston", "port", "US", 29.76, -95.27, ["crude_oil", "lng"], 270, 3.0, 3),
    ("qingdao_port", "Port of Qingdao", "port", "CN", 36.07, 120.38, ["iron_ore", "crude_oil"], 600, 6.0, 3),
    ("dampier_port", "Port of Dampier", "port", "AU", -20.66, 116.71, ["iron_ore", "lng"], 180, 15.0, 4),
    ("santos_port", "Port of Santos", "port", "BR", -23.95, -46.3, ["iron_ore", "crude_oil"], 130, 2.0, 3),
    ("gladstone_port", "Port of Gladstone", "port", "AU", -23.84, 151.27, ["coal", "lng"], 120, 10.0, 4),
    ("fujairah_port", "Port of Fujairah", "port", "AE", 25.12, 56.35, ["crude_oil"], 100, 2.0, 4),
    ("druzhba_pipeline", "Druzhba Pipeline", "pipeline", "RU", 52.97, 36.07, ["crude_oil"], 60, 1.5, 7),
    ("nord_stream", "Nord Stream", "pipeline", "RU", 59.73, 28.05, ["lng"], 55, 1.5, 9),
    ("trans_siberian_rail", "Trans-Siberian Railway", "rail", "RU", 55.75, 37.62, ["coal", "iron_ore"], 100, 2.0, 5),
    ("pilbara_rail", "Pilbara Railway Network", "rail", "AU", -22.3, 118.0, ["iron_ore"], 500, 40.0, 4),
    ("hunter_valley_rail", "Hunter Valley Coal Chain", "rail", "AU", -32.7, 151.5, ["coal"], 160, 30.0, 5),
]


def _parse_wpi_row(row: dict) -> dict | None:
    """Parse a WPI CSV row into ports table format."""
    try:
        lat = float(row.get("Latitude", 0))
        lon = float(row.get("Longitude", 0))
        if lat == 0 and lon == 0:
            return None

        name = row.get("Main Port Name", "").strip()
        if not name:
            return None

        wpi_number = int(row.get("World Port Index Number", 0)) or None
        country = row.get("Country Code", "").strip()[:2]
        region = row.get("World Water Body", "").strip() or None
        harbor_type = row.get("Harbor Type", "").strip() or None

        # Determine if major
        major_info = MAJOR_PORTS.get(name, {})
        commodities = major_info.get("commodities", [])
        annual_mt = major_info.get("annual_mt")
        is_major = bool(major_info)

        return {
            "wpi_number": wpi_number,
            "name": name,
            "country_code": country,
            "latitude": lat,
            "longitude": lon,
            "region": region,
            "harbor_type": harbor_type,
            "commodities": commodities or None,
            "annual_throughput_mt": annual_mt,
            "is_major": is_major,
            "is_chokepoint": False,
        }
    except (ValueError, KeyError) as e:
        logger.warning("Skipping WPI row: %s", e)
        return None


def seed_ports():
    """Download WPI CSV and seed ports table."""
    logger.info("Downloading World Port Index CSV...")
    try:
        resp = httpx.get(WPI_CSV_URL, timeout=60, follow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        logger.error("Failed to download WPI CSV: %s", e)
        logger.info("You can manually download from: %s", WPI_CSV_URL)
        return 0

    reader = csv.DictReader(io.StringIO(resp.text))
    ports = []
    for row in reader:
        parsed = _parse_wpi_row(row)
        if parsed:
            ports.append(parsed)

    logger.info("Parsed %d ports from WPI CSV", len(ports))

    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        with conn.cursor() as cur:
            values = [
                (
                    p["wpi_number"], p["name"], p["country_code"],
                    p["latitude"], p["longitude"], p["region"],
                    p["harbor_type"], p["commodities"],
                    p["annual_throughput_mt"], p["is_major"], p["is_chokepoint"],
                )
                for p in ports
            ]
            execute_values(
                cur,
                """
                INSERT INTO ports (wpi_number, name, country_code, latitude, longitude,
                                   region, harbor_type, commodities, annual_throughput_mt,
                                   is_major, is_chokepoint)
                VALUES %s
                ON CONFLICT (wpi_number) DO UPDATE SET
                    name = EXCLUDED.name,
                    country_code = EXCLUDED.country_code,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    region = EXCLUDED.region,
                    harbor_type = EXCLUDED.harbor_type,
                    commodities = COALESCE(EXCLUDED.commodities, ports.commodities),
                    annual_throughput_mt = COALESCE(EXCLUDED.annual_throughput_mt, ports.annual_throughput_mt),
                    is_major = EXCLUDED.is_major OR ports.is_major,
                    updated_at = NOW()
                """,
                values,
            )
            conn.commit()
            logger.info("Upserted %d ports", len(values))
    finally:
        conn.close()

    return len(ports)


def seed_bottleneck_nodes():
    """Seed bottleneck_nodes table."""
    logger.info("Seeding %d bottleneck nodes...", len(BOTTLENECK_NODES))

    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO bottleneck_nodes (slug, name, type, country_code,
                    latitude, longitude, commodities, annual_volume_mt,
                    global_share_pct, baseline_risk)
                VALUES %s
                ON CONFLICT (slug) DO UPDATE SET
                    name = EXCLUDED.name,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    commodities = EXCLUDED.commodities,
                    annual_volume_mt = EXCLUDED.annual_volume_mt,
                    global_share_pct = EXCLUDED.global_share_pct,
                    baseline_risk = EXCLUDED.baseline_risk,
                    updated_at = NOW()
                """,
                BOTTLENECK_NODES,
            )
            conn.commit()
            logger.info("Upserted %d bottleneck nodes", len(BOTTLENECK_NODES))
    finally:
        conn.close()


if __name__ == "__main__":
    count = seed_ports()
    seed_bottleneck_nodes()
    logger.info("Done! %d ports + %d bottleneck nodes seeded", count, len(BOTTLENECK_NODES))
