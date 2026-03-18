"""Seed infrastructure_assets table with ~50 key energy infrastructure assets.

Usage:
    docker compose exec backend python -m scripts.seed_infrastructure
"""

import logging
import sys

import psycopg2
from psycopg2.extras import execute_values

from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# (name, type, lat, lon, status, capacity, capacity_unit, commodities, country_code, description)
INFRASTRUCTURE_ASSETS = [
    # ── LNG Terminals ──
    ("Sabine Pass LNG", "lng_terminal", 29.74, -93.86, "operational", 30.0, "mtpa", ["lng"], "US", "Largest US LNG export terminal, operated by Cheniere Energy"),
    ("Ras Laffan LNG", "lng_terminal", 25.91, 51.53, "operational", 77.0, "mtpa", ["lng"], "QA", "World's largest LNG export facility"),
    ("Gladstone LNG", "lng_terminal", -23.85, 151.28, "operational", 7.8, "mtpa", ["lng"], "AU", "Santos GLNG export terminal"),
    ("Yamal LNG", "lng_terminal", 71.26, 72.94, "operational", 16.5, "mtpa", ["lng"], "RU", "Arctic LNG facility operated by Novatek"),
    ("Freeport LNG", "lng_terminal", 28.94, -95.31, "operational", 15.0, "mtpa", ["lng"], "US", "Major US Gulf Coast LNG terminal"),
    ("Cameron LNG", "lng_terminal", 29.77, -93.33, "operational", 13.5, "mtpa", ["lng"], "US", "Sempra Energy LNG export facility"),
    ("Bonny Island LNG", "lng_terminal", 4.42, 7.15, "operational", 22.0, "mtpa", ["lng"], "NG", "Nigeria LNG, Africa's largest LNG plant"),
    ("Bintulu LNG", "lng_terminal", 3.26, 113.07, "operational", 29.3, "mtpa", ["lng"], "MY", "Petronas LNG complex in Sarawak"),
    ("Gate Terminal Rotterdam", "lng_terminal", 51.88, 4.05, "operational", 12.0, "mtpa", ["lng"], "NL", "Europe's largest LNG import terminal"),
    ("Dahej LNG", "lng_terminal", 21.71, 72.58, "operational", 17.5, "mtpa", ["lng"], "IN", "India's largest LNG import terminal"),
    ("Incheon LNG", "lng_terminal", 37.45, 126.60, "operational", 40.0, "mtpa", ["lng"], "KR", "KOGAS LNG receiving terminal"),
    ("Montoir-de-Bretagne LNG", "lng_terminal", 47.30, -2.14, "operational", 10.0, "mtpa", ["lng"], "FR", "France's primary LNG import terminal"),

    # ── Refineries ──
    ("Jamnagar Refinery", "refinery", 22.25, 69.07, "operational", 1.24, "mbd", ["crude_oil"], "IN", "World's largest refinery complex, Reliance Industries"),
    ("Ruwais Refinery", "refinery", 24.11, 52.73, "operational", 0.92, "mbd", ["crude_oil"], "AE", "ADNOC flagship refinery in Abu Dhabi"),
    ("SK Ulsan Refinery", "refinery", 35.50, 129.38, "operational", 0.84, "mbd", ["crude_oil"], "KR", "SK Innovation refinery, one of Asia's largest"),
    ("Rotterdam Refinery (Shell)", "refinery", 51.89, 4.32, "operational", 0.40, "mbd", ["crude_oil"], "NL", "Shell Pernis, Europe's largest refinery"),
    ("Port Arthur Refinery", "refinery", 29.86, -93.97, "operational", 0.63, "mbd", ["crude_oil"], "US", "Motiva refinery, largest in US"),
    ("Ras Tanura Refinery", "refinery", 26.64, 50.15, "operational", 0.55, "mbd", ["crude_oil"], "SA", "Saudi Aramco refinery complex"),
    ("Jurong Island Refinery", "refinery", 1.26, 103.69, "operational", 0.59, "mbd", ["crude_oil"], "SG", "ExxonMobil Singapore, major Asian refining hub"),
    ("Baytown Refinery", "refinery", 29.73, -95.01, "operational", 0.56, "mbd", ["crude_oil"], "US", "ExxonMobil Baytown complex"),
    ("Paraguana Refinery", "refinery", 11.74, -70.22, "operational", 0.96, "mbd", ["crude_oil"], "VE", "PDVSA Paraguana complex, often reduced capacity"),

    # ── Pipeline Endpoints ──
    ("LOOP (Louisiana Offshore Oil Port)", "pipeline", 28.88, -90.03, "operational", 1.80, "mbd", ["crude_oil"], "US", "Only US deepwater oil port, handles VLCCs"),
    ("East-West Pipeline Yanbu", "pipeline", 24.09, 38.06, "operational", 5.00, "mbd", ["crude_oil"], "SA", "Petroline terminal, Red Sea bypass for Hormuz"),
    ("Ceyhan Terminal", "pipeline", 36.88, 35.95, "operational", 1.60, "mbd", ["crude_oil"], "TR", "BTC pipeline terminus on Mediterranean"),
    ("Druzhba Pipeline Schwedt", "pipeline", 53.04, 14.28, "operational", 0.50, "mbd", ["crude_oil"], "DE", "Western terminus of Druzhba pipeline"),
    ("ESPO Pipeline Kozmino", "pipeline", 42.74, 133.07, "operational", 1.60, "mbd", ["crude_oil"], "RU", "Pacific terminus, Russian crude to Asia"),
    ("Trans Mountain Burnaby", "pipeline", 49.28, -122.95, "operational", 0.89, "mbd", ["crude_oil"], "CA", "Trans Mountain pipeline terminus to Pacific"),
    ("Cushing Oil Hub", "pipeline", 35.98, -96.77, "operational", 90.0, "mb_storage", ["crude_oil"], "US", "WTI pricing hub, major pipeline intersection"),

    # ── Coal Ports ──
    ("Newcastle Coal Terminal", "coal_port", -32.92, 151.78, "operational", 212.0, "mtpa", ["coal"], "AU", "World's largest coal export port"),
    ("Hay Point Coal Terminal", "coal_port", -21.28, 149.30, "operational", 110.0, "mtpa", ["coal"], "AU", "Major Queensland met coal terminal"),
    ("Richards Bay Coal Terminal", "coal_port", -28.78, 32.08, "operational", 91.0, "mtpa", ["coal"], "ZA", "Africa's largest coal export terminal"),
    ("Qinhuangdao Coal Port", "coal_port", 39.93, 119.59, "operational", 250.0, "mtpa", ["coal"], "CN", "China's largest coal port"),
    ("Dalrymple Bay Coal Terminal", "coal_port", -21.34, 149.23, "operational", 85.0, "mtpa", ["coal"], "AU", "Queensland met coal export facility"),
    ("Gladstone Coal Terminal", "coal_port", -23.83, 151.27, "operational", 68.0, "mtpa", ["coal"], "AU", "Multi-user coal terminal in Queensland"),
    ("Tanjung Bara Coal Terminal", "coal_port", 1.20, 117.46, "operational", 50.0, "mtpa", ["coal"], "ID", "Kaltim Prima Coal export terminal, East Kalimantan"),
    ("Muara Pantai Coal Terminal", "coal_port", -3.80, 114.80, "operational", 35.0, "mtpa", ["coal"], "ID", "Adaro Energy coal export hub, South Kalimantan"),

    # ── Oil Fields (major offshore/onshore complexes) ──
    ("Ghawar Field", "oil_field", 24.50, 49.25, "operational", 3.80, "mbd", ["crude_oil"], "SA", "World's largest conventional oil field"),
    ("Permian Basin Midland", "oil_field", 32.00, -102.08, "operational", 5.70, "mbd", ["crude_oil"], "US", "Largest US oil producing region"),
    ("Kashagan Field", "oil_field", 46.24, 51.70, "operational", 0.40, "mbd", ["crude_oil"], "KZ", "Giant Caspian Sea offshore field"),
    ("Tupi/Lula Field", "oil_field", -25.50, -42.90, "operational", 1.00, "mbd", ["crude_oil"], "BR", "Petrobras pre-salt deep-water field"),
    ("Cantarell Field", "oil_field", 19.77, -91.98, "operational", 0.14, "mbd", ["crude_oil"], "MX", "Giant offshore field in Bay of Campeche, declining"),
    ("North West Shelf", "oil_field", -19.59, 116.14, "operational", 0.30, "mbd", ["crude_oil", "lng"], "AU", "Major Australian offshore LNG/condensate complex"),

    # ── Storage Facilities ──
    ("Fujairah Oil Terminal", "storage", 25.12, 56.35, "operational", 60.0, "mb_storage", ["crude_oil"], "AE", "Largest commercial oil storage hub outside US/NL"),
    ("Saldanha Bay SFF", "storage", -33.00, 17.88, "operational", 45.0, "mb_storage", ["crude_oil"], "ZA", "South Africa strategic fuel storage"),
    ("Jurong Rock Caverns", "storage", 1.25, 103.70, "operational", 9.3, "mb_storage", ["crude_oil"], "SG", "Southeast Asia's first underground oil storage"),
    ("Kiire Oil Storage", "storage", 31.39, 130.57, "operational", 30.0, "mb_storage", ["crude_oil"], "JP", "Japan national strategic petroleum reserve"),
    ("Sture Terminal", "storage", 60.60, 5.03, "operational", 2.0, "mb_storage", ["crude_oil"], "NO", "Equinor crude oil terminal, North Sea"),
    ("Okinawa CTS", "storage", 26.33, 127.77, "operational", 6.0, "mb_storage", ["crude_oil"], "JP", "Japan's largest commercial crude oil storage"),
]


def seed_infrastructure():
    """Insert infrastructure assets into the database."""
    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        with conn.cursor() as cur:
            # Create table if not exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS infrastructure_assets (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    type TEXT NOT NULL,
                    name TEXT NOT NULL UNIQUE,
                    latitude NUMERIC(9,6) NOT NULL,
                    longitude NUMERIC(10,6) NOT NULL,
                    status TEXT NOT NULL DEFAULT 'operational',
                    capacity NUMERIC(12,2),
                    capacity_unit TEXT,
                    commodities TEXT[] NOT NULL DEFAULT '{}',
                    country_code TEXT,
                    description TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

            # Create indexes
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_infrastructure_type ON infrastructure_assets (type);
                CREATE INDEX IF NOT EXISTS idx_infrastructure_commodities ON infrastructure_assets USING GIN (commodities);
                CREATE INDEX IF NOT EXISTS idx_infrastructure_bbox ON infrastructure_assets (latitude, longitude);
            """)

            # Upsert assets
            values = [
                (name, type_, lat, lon, status, capacity, cap_unit, commodities, country, desc)
                for name, type_, lat, lon, status, capacity, cap_unit, commodities, country, desc
                in INFRASTRUCTURE_ASSETS
            ]

            execute_values(
                cur,
                """
                INSERT INTO infrastructure_assets (name, type, latitude, longitude, status, capacity, capacity_unit, commodities, country_code, description)
                VALUES %s
                ON CONFLICT (name) DO UPDATE SET
                    type = EXCLUDED.type,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    status = EXCLUDED.status,
                    capacity = EXCLUDED.capacity,
                    capacity_unit = EXCLUDED.capacity_unit,
                    commodities = EXCLUDED.commodities,
                    country_code = EXCLUDED.country_code,
                    description = EXCLUDED.description,
                    updated_at = NOW()
                """,
                values,
            )
            conn.commit()

            cur.execute("SELECT COUNT(*) FROM infrastructure_assets")
            count = cur.fetchone()[0]
            logger.info("Seeded infrastructure_assets: %d total rows", count)
            return {"seeded": len(values), "total": count}
    finally:
        conn.close()


if __name__ == "__main__":
    result = seed_infrastructure()
    print(f"Done: {result}")
