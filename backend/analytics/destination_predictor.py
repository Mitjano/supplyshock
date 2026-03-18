"""Destination prediction for active voyages — Issue #46.

Uses historical voyage patterns to predict the most likely destination port
for underway voyages. Falls back to AIS-reported destination when no
historical data is available.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def predict_destination(
    db: AsyncSession, voyage_id: str
) -> dict[str, Any]:
    """Predict the destination port for a given voyage.

    Strategy:
    1. Look up the voyage to get origin_port_id, vessel_type, cargo_type.
    2. Query historical completed voyages from the same origin with matching
       vessel_type and cargo_type.
    3. Rank destinations by frequency; confidence = matches / total from
       same origin.
    4. If no historical data, fall back to the AIS destination field from
       vessel_positions.

    Returns a dict with predicted_port_id, predicted_port_name, confidence,
    method, and alternatives.
    """
    # ── Step 1: fetch the voyage ──────────────────────────────────────
    result = await db.execute(
        text("""
            SELECT v.id, v.origin_port_id, v.vessel_type,
                   v.cargo_type, v.mmsi
            FROM voyages v
            WHERE v.id = :voyage_id
        """),
        {"voyage_id": voyage_id},
    )
    voyage = result.mappings().first()
    if not voyage:
        return {
            "predicted_port_id": None,
            "predicted_port_name": None,
            "confidence": 0.0,
            "method": "historical",
            "alternatives": [],
            "error": "Voyage not found",
        }

    origin_port_id = voyage["origin_port_id"]
    vessel_type = voyage["vessel_type"]
    cargo_type = voyage["cargo_type"]
    mmsi = voyage["mmsi"]

    # ── Step 2: historical prediction ─────────────────────────────────
    if origin_port_id and vessel_type and cargo_type:
        prediction = await _predict_from_history(
            db, origin_port_id, vessel_type, cargo_type
        )
        if prediction is not None:
            return prediction

    # ── Step 3: AIS fallback ──────────────────────────────────────────
    return await _predict_from_ais(db, mmsi)


async def _predict_from_history(
    db: AsyncSession,
    origin_port_id: str,
    vessel_type: str,
    cargo_type: str,
) -> dict[str, Any] | None:
    """Predict destination from historical completed voyage patterns."""
    # Total completed voyages from same origin
    total_result = await db.execute(
        text("""
            SELECT COUNT(*) AS cnt
            FROM voyages
            WHERE origin_port_id = :origin_port_id
              AND status = 'completed'
        """),
        {"origin_port_id": origin_port_id},
    )
    total_from_origin = total_result.scalar() or 0
    if total_from_origin == 0:
        return None

    # Destination frequency for matching vessel_type + cargo_type
    result = await db.execute(
        text("""
            SELECT v.dest_port_id,
                   p.name AS dest_port_name,
                   COUNT(*) AS cnt
            FROM voyages v
            JOIN ports p ON p.id = v.dest_port_id
            WHERE v.origin_port_id = :origin_port_id
              AND v.vessel_type = :vessel_type::vessel_type
              AND v.cargo_type = :cargo_type
              AND v.status = 'completed'
              AND v.dest_port_id IS NOT NULL
            GROUP BY v.dest_port_id, p.name
            ORDER BY cnt DESC
        """),
        {
            "origin_port_id": origin_port_id,
            "vessel_type": vessel_type,
            "cargo_type": cargo_type,
        },
    )
    rows = result.mappings().all()
    if not rows:
        return None

    total_matching = sum(r["cnt"] for r in rows)

    top = rows[0]
    alternatives = [
        {
            "port_id": str(r["dest_port_id"]),
            "name": r["dest_port_name"],
            "probability": round(r["cnt"] / total_matching, 4),
        }
        for r in rows[1:]
    ]

    return {
        "predicted_port_id": str(top["dest_port_id"]),
        "predicted_port_name": top["dest_port_name"],
        "confidence": round(total_matching / total_from_origin, 4),
        "method": "historical",
        "alternatives": alternatives,
    }


async def _predict_from_ais(
    db: AsyncSession, mmsi: int | None
) -> dict[str, Any]:
    """Fall back to AIS-reported destination from vessel_positions."""
    if mmsi is None:
        return {
            "predicted_port_id": None,
            "predicted_port_name": None,
            "confidence": 0.0,
            "method": "ais_fallback",
            "alternatives": [],
        }

    result = await db.execute(
        text("""
            SELECT vp.destination, p.id AS port_id, p.name AS port_name
            FROM vessel_positions vp
            LEFT JOIN ports p ON UPPER(p.name) = UPPER(vp.destination)
            WHERE vp.mmsi = :mmsi
              AND vp.destination IS NOT NULL
              AND vp.destination != ''
            ORDER BY vp.timestamp DESC
            LIMIT 1
        """),
        {"mmsi": mmsi},
    )
    row = result.mappings().first()

    if not row or not row["destination"]:
        return {
            "predicted_port_id": None,
            "predicted_port_name": None,
            "confidence": 0.0,
            "method": "ais_fallback",
            "alternatives": [],
        }

    return {
        "predicted_port_id": str(row["port_id"]) if row["port_id"] else None,
        "predicted_port_name": row["port_name"] or row["destination"],
        "confidence": 0.0,
        "method": "ais_fallback",
        "alternatives": [],
    }


# ── Batch update (Celery Beat hourly) ────────────────────────────────


async def update_voyage_predictions(db: AsyncSession) -> dict[str, Any]:
    """Batch-update destination predictions for all active (underway) voyages.

    Intended to be called by Celery Beat on an hourly schedule.
    Returns a summary dict with counts of updated and failed voyages.
    """
    result = await db.execute(
        text("""
            SELECT id FROM voyages WHERE status = 'underway'
        """),
    )
    voyage_ids = [str(row["id"]) for row in result.mappings().all()]

    updated = 0
    failed = 0

    for vid in voyage_ids:
        try:
            prediction = await predict_destination(db, vid)

            if prediction.get("predicted_port_id"):
                await db.execute(
                    text("""
                        UPDATE voyages
                        SET predicted_dest_port_id = :port_id,
                            predicted_dest_confidence = :confidence,
                            predicted_dest_method = :method
                        WHERE id = :voyage_id
                    """),
                    {
                        "port_id": prediction["predicted_port_id"],
                        "confidence": prediction["confidence"],
                        "method": prediction["method"],
                        "voyage_id": vid,
                    },
                )
                updated += 1
            else:
                failed += 1
        except Exception:
            logger.exception("Failed to predict destination for voyage %s", vid)
            failed += 1

    await db.commit()

    logger.info(
        "Destination predictions updated: %d success, %d failed out of %d active voyages",
        updated, failed, len(voyage_ids),
    )

    return {
        "total_active": len(voyage_ids),
        "updated": updated,
        "failed": failed,
    }
