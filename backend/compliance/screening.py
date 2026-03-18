"""Vessel sanctions screening.

Checks a vessel (by MMSI, IMO, or name) against the local
`sanctioned_entities` table populated by ingestion/sanctions.py.
"""

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def screen_vessel(
    db: AsyncSession,
    mmsi: int,
    imo: int | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """Screen a single vessel against sanctioned_entities.

    Matching strategy (in priority order):
    1. Exact MMSI match
    2. Exact IMO match
    3. Fuzzy name match (trigram similarity > 0.4)

    Returns:
        {"sanctioned": bool, "matches": [{"source", "entity_name", "program", "match_type"}]}
    """
    matches: list[dict[str, Any]] = []

    # 1. MMSI match
    result = await db.execute(
        text("""
            SELECT source, entity_name, program
            FROM sanctioned_entities
            WHERE mmsi = :mmsi
        """),
        {"mmsi": mmsi},
    )
    for row in result.mappings().all():
        matches.append({
            "source": row["source"],
            "entity_name": row["entity_name"],
            "program": row["program"],
            "match_type": "mmsi_exact",
        })

    # 2. IMO match
    if imo:
        result = await db.execute(
            text("""
                SELECT source, entity_name, program
                FROM sanctioned_entities
                WHERE imo = :imo
            """),
            {"imo": imo},
        )
        for row in result.mappings().all():
            # Avoid duplicates if already matched by MMSI
            key = (row["source"], row["entity_name"])
            if not any((m["source"], m["entity_name"]) == key for m in matches):
                matches.append({
                    "source": row["source"],
                    "entity_name": row["entity_name"],
                    "program": row["program"],
                    "match_type": "imo_exact",
                })

    # 3. Fuzzy name match (requires pg_trgm extension)
    if name:
        result = await db.execute(
            text("""
                SELECT source, entity_name, program,
                       similarity(UPPER(entity_name), UPPER(:name)) AS sim
                FROM sanctioned_entities
                WHERE similarity(UPPER(entity_name), UPPER(:name)) > 0.4
                ORDER BY sim DESC
                LIMIT 5
            """),
            {"name": name},
        )
        for row in result.mappings().all():
            key = (row["source"], row["entity_name"])
            if not any((m["source"], m["entity_name"]) == key for m in matches):
                matches.append({
                    "source": row["source"],
                    "entity_name": row["entity_name"],
                    "program": row["program"],
                    "match_type": f"name_fuzzy (sim={row['sim']:.2f})",
                })

    return {
        "sanctioned": len(matches) > 0,
        "matches": matches,
    }
