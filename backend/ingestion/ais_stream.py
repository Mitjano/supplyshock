"""AIS vessel position and static data ingestion from aisstream.io WebSocket.

Connects to wss://stream.aisstream.io/v0/stream, parses:
  - Position reports (AIS types 1, 2, 3, 18) → vessel_positions hypertable
  - Ship static data  (AIS type 5)           → vessel_static_data table (UPSERT)

Batch-inserts positions every BATCH_INTERVAL seconds.
Static data is upserted immediately (low volume — ~1 msg per vessel per 6 min).
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

# AIS Type 5 message type
STATIC_DATA_MESSAGE_TYPE = "ShipStaticData"

# Block coefficient by vessel type — used for DWT estimation
# DWT ≈ length × beam × draught × Cb
CB_BY_TYPE = {
    "tanker": 0.85,
    "bulk_carrier": 0.83,
    "container": 0.65,
    "lng_carrier": 0.78,
    "general_cargo": 0.72,
    "passenger": 0.60,
    "other": 0.70,
}

# Map aisstream vessel type codes to our vessel_type enum
# AIS ship type ranges:
#   60-69 = passenger vessels
#   70-79 = cargo (71-74 are typically containers, 75-79 other cargo/bulk)
#   80-89 = tanker
VESSEL_TYPE_MAP = {
    # Passenger vessels (AIS 60-69)
    range(60, 70): "passenger",
    # Container ships (AIS 71-74 — cellular container ships)
    range(71, 75): "container",
    # Bulk carriers and general cargo (AIS 70 and 75-79)
    # Note: AIS 70 = "cargo, all ships of this type"
    # We map 70 and 75-79 as bulk_carrier (best available approximation)
    range(75, 80): "bulk_carrier",
    # Tanker (AIS 80-89)
    range(80, 90): "tanker",
}

# LNG carriers: AIS type 84 specifically = tanker, liquefied gas
# Override tanker range for this specific subtype
_AIS_LNG_TYPES = {84}

# Special case: AIS type 70 = generic cargo, map to bulk_carrier
_AIS_TYPE_70 = "bulk_carrier"


def _map_vessel_type(ais_type: int | None) -> str:
    """Map AIS ship type code to our vessel_type enum."""
    if ais_type is None:
        return "other"
    # LNG carriers (AIS 84 = liquefied gas tanker)
    if ais_type in _AIS_LNG_TYPES:
        return "lng_carrier"
    # Handle AIS type 70 specifically (generic cargo)
    if ais_type == 70:
        return _AIS_TYPE_70
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
            "cargo_type": str(meta.get("ShipType")) if meta.get("ShipType") else None,
        }
    except Exception as e:
        logger.warning("Failed to parse AIS message: %s", e)
        return None


def _estimate_dwt(length: float, beam: float, draught: float, vessel_type: str) -> float | None:
    """Estimate DWT from vessel dimensions using block coefficient.

    Formula: DWT ≈ L × B × T × Cb × seawater_density(1.025) × 0.65(DWT/displacement ratio)
    Simplified: DWT ≈ L × B × T × Cb_adjusted
    """
    if not all([length, beam, draught]) or length <= 0 or beam <= 0 or draught <= 0:
        return None
    cb = CB_BY_TYPE.get(vessel_type, 0.70)
    # Displacement = L × B × T × Cb × 1.025 (seawater)
    # DWT ≈ 65% of displacement for cargo vessels
    dwt = length * beam * draught * cb * 1.025 * 0.65
    return round(dwt, 2)


def _parse_static_data(msg: dict) -> dict | None:
    """Parse AIS Type 5 (ShipStaticData) message into vessel_static_data row.

    Returns None if message is invalid or missing MMSI.
    """
    try:
        meta = msg.get("MetaData", {})
        message = msg.get("Message", {})
        report = message.get(STATIC_DATA_MESSAGE_TYPE)

        if not report:
            return None

        mmsi = meta.get("MMSI")
        if not mmsi:
            return None

        ship_type = meta.get("ShipType") or report.get("Type")
        vessel_type = _map_vessel_type(ship_type)

        # Dimensions from Type 5 message
        dimension = report.get("Dimension", {})
        dim_a = dimension.get("A")  # bow to antenna
        dim_b = dimension.get("B")  # antenna to stern
        dim_c = dimension.get("C")  # port to antenna
        dim_d = dimension.get("D")  # antenna to starboard

        length_m = None
        beam_m = None
        if dim_a is not None and dim_b is not None:
            length_m = dim_a + dim_b
        if dim_c is not None and dim_d is not None:
            beam_m = dim_c + dim_d

        max_draught = report.get("MaximumStaticDraught")
        # AIS sends draught in 1/10 metre — aisstream may pre-convert
        if max_draught and max_draught > 50:
            max_draught = max_draught / 10.0

        dwt_estimate = None
        if length_m and beam_m and max_draught:
            dwt_estimate = _estimate_dwt(length_m, beam_m, max_draught, vessel_type)

        return {
            "mmsi": mmsi,
            "imo": report.get("ImoNumber") or meta.get("IMO"),
            "vessel_name": (meta.get("ShipName") or report.get("Name", "")).strip() or None,
            "callsign": (report.get("CallSign") or "").strip() or None,
            "ship_type": ship_type,
            "vessel_type": vessel_type,
            "dim_a": dim_a,
            "dim_b": dim_b,
            "dim_c": dim_c,
            "dim_d": dim_d,
            "length_m": length_m,
            "beam_m": beam_m,
            "dwt_estimate": dwt_estimate,
            "max_draught": max_draught,
            "flag_country": meta.get("country"),
        }
    except Exception as e:
        logger.warning("Failed to parse AIS Type 5 message: %s", e)
        return None


async def _upsert_static_data(session: AsyncSession, data: dict) -> None:
    """UPSERT a single vessel_static_data row.

    Updates all fields on conflict (MMSI already exists).
    """
    await session.execute(
        text("""
            INSERT INTO vessel_static_data (
                mmsi, imo, vessel_name, callsign, ship_type, vessel_type,
                dim_a, dim_b, dim_c, dim_d, length_m, beam_m,
                dwt_estimate, max_draught, flag_country
            ) VALUES (
                :mmsi, :imo, :vessel_name, :callsign, :ship_type, :vessel_type,
                :dim_a, :dim_b, :dim_c, :dim_d, :length_m, :beam_m,
                :dwt_estimate, :max_draught, :flag_country
            )
            ON CONFLICT (mmsi) DO UPDATE SET
                imo          = COALESCE(EXCLUDED.imo, vessel_static_data.imo),
                vessel_name  = COALESCE(EXCLUDED.vessel_name, vessel_static_data.vessel_name),
                callsign     = COALESCE(EXCLUDED.callsign, vessel_static_data.callsign),
                ship_type    = COALESCE(EXCLUDED.ship_type, vessel_static_data.ship_type),
                vessel_type  = EXCLUDED.vessel_type,
                dim_a        = COALESCE(EXCLUDED.dim_a, vessel_static_data.dim_a),
                dim_b        = COALESCE(EXCLUDED.dim_b, vessel_static_data.dim_b),
                dim_c        = COALESCE(EXCLUDED.dim_c, vessel_static_data.dim_c),
                dim_d        = COALESCE(EXCLUDED.dim_d, vessel_static_data.dim_d),
                length_m     = COALESCE(EXCLUDED.length_m, vessel_static_data.length_m),
                beam_m       = COALESCE(EXCLUDED.beam_m, vessel_static_data.beam_m),
                dwt_estimate = COALESCE(EXCLUDED.dwt_estimate, vessel_static_data.dwt_estimate),
                max_draught  = COALESCE(EXCLUDED.max_draught, vessel_static_data.max_draught),
                flag_country = COALESCE(EXCLUDED.flag_country, vessel_static_data.flag_country),
                updated_at   = NOW()
        """),
        data,
    )
    await session.commit()


async def _flush_batch(session: AsyncSession, batch: list[dict]) -> int:
    """Batch insert positions into vessel_positions. Returns count inserted.

    TimescaleDB hypertables handle duplicates via the time+mmsi combination
    (the hypertable chunk partitioning + unique index on (time, mmsi) if configured).
    If no unique constraint exists, duplicates are possible but harmless for
    time-series data — each position report is a distinct observation.
    """
    if not batch:
        return 0

    # Use ON CONFLICT DO NOTHING if a unique constraint on (time, mmsi) exists;
    # otherwise this is a plain insert (safe for hypertables without unique constraint).
    await session.execute(
        text("""
            INSERT INTO vessel_positions (
                time, mmsi, imo, vessel_name, vessel_type,
                latitude, longitude, speed_knots, course, heading,
                destination, draught, flag_country, cargo_type
            ) VALUES (
                :time, :mmsi, :imo, :vessel_name, :vessel_type,
                :latitude, :longitude, :speed_knots, :course, :heading,
                :destination, :draught, :flag_country, :cargo_type
            )
            ON CONFLICT DO NOTHING
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
                # Subscribe to position reports + static data for all areas
                subscribe_msg = {
                    "APIKey": api_key,
                    "BoundingBoxes": [[[-90, -180], [90, 180]]],  # Entire world
                    "FilterMessageTypes": [
                        "PositionReport",
                        "StandardClassBPositionReport",
                        "ShipStaticData",
                    ],
                }
                await ws.send(json.dumps(subscribe_msg))
                logger.info("Subscribed to aisstream.io — receiving positions + static data")

                reconnect_delay = RECONNECT_BASE  # Reset on successful connect
                batch: list[dict] = []
                last_flush = time.monotonic()
                total_inserted = 0
                total_static = 0
                last_log = time.monotonic()

                async for raw_msg in ws:
                    msg = json.loads(raw_msg)
                    msg_type = msg.get("MessageType", "")

                    # AIS Type 5 — static data (low volume, upsert immediately)
                    if msg_type == STATIC_DATA_MESSAGE_TYPE:
                        static = _parse_static_data(msg)
                        if static:
                            try:
                                async with session_factory() as session:
                                    await _upsert_static_data(session, static)
                                total_static += 1
                            except Exception as e:
                                logger.warning("Failed to upsert static data for MMSI %s: %s",
                                               static.get("mmsi"), e)
                        continue

                    # Position reports — batch insert
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
                            "AIS stats: %d positions, %d static updates in last minute, buffer=%d",
                            total_inserted,
                            total_static,
                            len(batch),
                        )
                        total_inserted = 0
                        total_static = 0
                        last_log = now

        except websockets.exceptions.ConnectionClosed as e:
            logger.warning("AIS WebSocket closed: %s — reconnecting in %ds", e, reconnect_delay)
        except Exception as e:
            logger.error("AIS consumer error: %s — reconnecting in %ds", e, reconnect_delay)

        await asyncio.sleep(reconnect_delay)
        reconnect_delay = min(reconnect_delay * 2, RECONNECT_MAX)
