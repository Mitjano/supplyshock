"""AIS vessel position ingestion from aisstream.io WebSocket.

Connects to wss://stream.aisstream.io/v0/stream, parses position reports
(AIS message types 1, 2, 3, 18), and batch-inserts into vessel_positions
hypertable every BATCH_INTERVAL seconds.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone

import websockets
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from config import settings

logger = logging.getLogger(__name__)

WS_URL = "wss://stream.aisstream.io/v0/stream"
BATCH_INTERVAL = 5  # seconds — flush buffer to DB
RECONNECT_BASE = 1  # seconds — exponential backoff start
RECONNECT_MAX = 60  # seconds — max backoff

# AIS message types for position reports
POSITION_MESSAGE_TYPES = {"PositionReport", "StandardClassBPositionReport"}

# Map aisstream vessel type codes to our vessel_type enum
# AIS ship type first digit: 6=passenger, 7=cargo, 8=tanker
VESSEL_TYPE_MAP = {
    range(60, 70): "container",  # passenger — close enough
    range(70, 80): "bulk_carrier",
    range(80, 90): "tanker",
}


def _map_vessel_type(ais_type: int | None) -> str:
    """Map AIS ship type code to our vessel_type enum."""
    if ais_type is None:
        return "other"
    for type_range, vessel_type in VESSEL_TYPE_MAP.items():
        if ais_type in type_range:
            return vessel_type
    return "other"


def _parse_position(msg: dict) -> dict | None:
    """Parse aisstream message into vessel_positions row dict.

    Returns None if message is invalid or missing required fields.
    """
    try:
        meta = msg.get("MetaData", {})
        position_report = msg.get("Message", {})

        # Get the actual report — could be PositionReport or StandardClassBPositionReport
        report = None
        for key in POSITION_MESSAGE_TYPES:
            if key in position_report:
                report = position_report[key]
                break

        if not report:
            return None

        mmsi = meta.get("MMSI")
        if not mmsi:
            return None

        lat = meta.get("latitude", report.get("Latitude"))
        lon = meta.get("longitude", report.get("Longitude"))

        if lat is None or lon is None:
            return None

        # Skip invalid coordinates
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return None

        # Skip default/unknown position (0, 0)
        if lat == 0.0 and lon == 0.0:
            return None

        return {
            "time": meta.get("time_utc", datetime.now(timezone.utc).isoformat()),
            "mmsi": mmsi,
            "imo": meta.get("IMO"),
            "vessel_name": meta.get("ShipName", "").strip() or None,
            "vessel_type": _map_vessel_type(meta.get("ShipType")),
            "latitude": lat,
            "longitude": lon,
            "speed_knots": report.get("Sog"),
            "course": report.get("Cog"),
            "heading": report.get("TrueHeading") if report.get("TrueHeading", 511) != 511 else None,
            "destination": meta.get("Destination", "").strip() or None,
            "draught": meta.get("Draught"),
            "flag_country": meta.get("country"),
            "nav_status": report.get("NavigationalStatus"),
        }
    except Exception as e:
        logger.warning("Failed to parse AIS message: %s", e)
        return None


async def _flush_batch(session: AsyncSession, batch: list[dict]) -> int:
    """Batch insert positions into vessel_positions. Returns count inserted."""
    if not batch:
        return 0

    # Use executemany with parameterized query
    await session.execute(
        text("""
            INSERT INTO vessel_positions (
                time, mmsi, imo, vessel_name, vessel_type,
                latitude, longitude, speed_knots, course, heading,
                destination, draught, flag_country, nav_status
            ) VALUES (
                :time, :mmsi, :imo, :vessel_name, :vessel_type,
                :latitude, :longitude, :speed_knots, :course, :heading,
                :destination, :draught, :flag_country, :nav_status
            )
        """),
        batch,
    )
    await session.commit()
    return len(batch)


async def run_ais_consumer(api_key: str | None = None):
    """Main AIS consumer loop with auto-reconnect.

    Connects to aisstream.io, subscribes to all vessel types,
    and batch-inserts positions every BATCH_INTERVAL seconds.
    """
    api_key = api_key or settings.AISSTREAM_API_KEY
    if not api_key:
        logger.error("AISSTREAM_API_KEY not set — cannot start AIS consumer")
        return

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    reconnect_delay = RECONNECT_BASE

    while True:
        try:
            logger.info("Connecting to aisstream.io...")
            async with websockets.connect(WS_URL) as ws:
                # Subscribe to position reports for all areas
                subscribe_msg = {
                    "APIKey": api_key,
                    "BoundingBoxes": [[[-90, -180], [90, 180]]],  # Entire world
                    "FilterMessageTypes": ["PositionReport", "StandardClassBPositionReport"],
                }
                await ws.send(json.dumps(subscribe_msg))
                logger.info("Subscribed to aisstream.io — receiving positions")

                reconnect_delay = RECONNECT_BASE  # Reset on successful connect
                batch: list[dict] = []
                last_flush = time.monotonic()
                total_inserted = 0
                last_log = time.monotonic()

                async for raw_msg in ws:
                    msg = json.loads(raw_msg)
                    parsed = _parse_position(msg)
                    if parsed:
                        batch.append(parsed)

                    # Flush every BATCH_INTERVAL seconds
                    now = time.monotonic()
                    if now - last_flush >= BATCH_INTERVAL and batch:
                        async with session_factory() as session:
                            count = await _flush_batch(session, batch)
                            total_inserted += count
                        batch.clear()
                        last_flush = now

                    # Log stats every 60 seconds
                    if now - last_log >= 60:
                        logger.info(
                            "AIS stats: %d positions inserted in last minute, buffer=%d",
                            total_inserted,
                            len(batch),
                        )
                        total_inserted = 0
                        last_log = now

        except websockets.exceptions.ConnectionClosed as e:
            logger.warning("AIS WebSocket closed: %s — reconnecting in %ds", e, reconnect_delay)
        except Exception as e:
            logger.error("AIS consumer error: %s — reconnecting in %ds", e, reconnect_delay)

        await asyncio.sleep(reconnect_delay)
        reconnect_delay = min(reconnect_delay * 2, RECONNECT_MAX)
