"""OFAC + EU sanctions list ingestion.

Downloads and parses vessel-related sanctions entries from:
- US Treasury OFAC SDN list (CSV)
- EU consolidated sanctions (XML)

Upserts into `sanctioned_entities` table.
"""

import csv
import io
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx
import psycopg2
from psycopg2.extras import execute_values

from config import settings

logger = logging.getLogger(__name__)

OFAC_SDN_CSV_URL = (
    "https://www.treasury.gov/ofac/downloads/sdn.csv"
)
EU_SANCTIONS_XML_URL = (
    "https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content"
)


def import_ofac_sanctions() -> int:
    """Download OFAC SDN CSV and upsert vessel entries into sanctioned_entities.

    Returns the number of rows upserted.
    """
    logger.info("Downloading OFAC SDN list...")
    resp = httpx.get(OFAC_SDN_CSV_URL, timeout=120, follow_redirects=True)
    resp.raise_for_status()

    reader = csv.reader(io.StringIO(resp.text))
    rows = []

    for line in reader:
        # SDN CSV columns: ent_num, SDN_Name, SDN_Type, Program, Title,
        #                   Call_Sign, Vess_Type, Tonnage, GRT, Vess_Flag,
        #                   Vess_Owner, Remarks
        if len(line) < 12:
            continue

        sdn_type = line[2].strip().upper()
        if sdn_type not in ("VESSEL", "-0- VESSEL"):
            # We only care about vessel entities
            continue

        entity_name = line[1].strip()
        program = line[3].strip()
        remarks = line[11].strip() if len(line) > 11 else ""

        # Extract IMO and MMSI from remarks field
        imo = _extract_field(remarks, "IMO")
        mmsi = _extract_field(remarks, "MMSI")

        rows.append((
            "ofac",
            entity_name,
            program,
            int(imo) if imo and imo.isdigit() else None,
            int(mmsi) if mmsi and mmsi.isdigit() else None,
            line[9].strip() or None,   # flag
            line[6].strip() or None,   # vessel type
            remarks,
        ))

    if not rows:
        logger.warning("No vessel entries found in OFAC SDN list")
        return 0

    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO sanctioned_entities
                    (source, entity_name, program, imo, mmsi, flag, vessel_type, remarks, updated_at)
                VALUES %s
                ON CONFLICT (source, entity_name)
                DO UPDATE SET
                    program    = EXCLUDED.program,
                    imo        = EXCLUDED.imo,
                    mmsi       = EXCLUDED.mmsi,
                    flag       = EXCLUDED.flag,
                    vessel_type = EXCLUDED.vessel_type,
                    remarks    = EXCLUDED.remarks,
                    updated_at = EXCLUDED.updated_at
                """,
                [(s, n, p, i, m, f, v, r, datetime.now(timezone.utc))
                 for s, n, p, i, m, f, v, r in rows],
            )
            conn.commit()
            logger.info("OFAC sanctions: upserted %d vessel entries", len(rows))
            return len(rows)
    finally:
        conn.close()


def import_eu_sanctions() -> int:
    """Download EU consolidated sanctions XML and upsert vessel entries.

    Returns the number of rows upserted.
    """
    logger.info("Downloading EU sanctions list...")
    resp = httpx.get(EU_SANCTIONS_XML_URL, timeout=180, follow_redirects=True)
    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    ns = {
        "s": "http://eu.europa.eu/fsd/sanctions"
    }

    rows = []

    for entity in root.findall(".//s:sanctionEntity", ns):
        subject_type = entity.findtext("s:subjectType", default="", namespaces=ns)
        if "vessel" not in subject_type.lower() and "ship" not in subject_type.lower():
            # Try to detect vessels from identification documents
            imo_el = entity.find(".//s:identification[s:identificationTypeCode='IMO']", ns)
            if imo_el is None:
                continue

        # Entity name
        name_el = entity.find(".//s:nameAlias[@wholeName]", ns)
        entity_name = name_el.attrib.get("wholeName", "").strip() if name_el is not None else ""
        if not entity_name:
            continue

        # Programme
        programme_el = entity.find(".//s:programme", ns)
        program = programme_el.text.strip() if programme_el is not None and programme_el.text else "EU"

        # Extract IMO
        imo = None
        for ident in entity.findall(".//s:identification", ns):
            id_type = ident.findtext("s:identificationTypeCode", default="", namespaces=ns)
            id_val = ident.findtext("s:identificationTypeValue", default="", namespaces=ns)
            if not id_val:
                id_val = ident.findtext("s:number", default="", namespaces=ns)
            if "IMO" in id_type.upper() and id_val.strip().isdigit():
                imo = int(id_val.strip())
                break

        # Extract MMSI (less common in EU lists)
        mmsi = None
        for ident in entity.findall(".//s:identification", ns):
            id_type = ident.findtext("s:identificationTypeCode", default="", namespaces=ns)
            id_val = ident.findtext("s:identificationTypeValue", default="", namespaces=ns)
            if not id_val:
                id_val = ident.findtext("s:number", default="", namespaces=ns)
            if "MMSI" in id_type.upper() and id_val.strip().isdigit():
                mmsi = int(id_val.strip())
                break

        rows.append((
            "eu",
            entity_name,
            program,
            imo,
            mmsi,
            None,  # flag not reliably in EU XML
            None,  # vessel type
            "",
        ))

    if not rows:
        logger.warning("No vessel entries found in EU sanctions list")
        return 0

    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO sanctioned_entities
                    (source, entity_name, program, imo, mmsi, flag, vessel_type, remarks, updated_at)
                VALUES %s
                ON CONFLICT (source, entity_name)
                DO UPDATE SET
                    program    = EXCLUDED.program,
                    imo        = EXCLUDED.imo,
                    mmsi       = EXCLUDED.mmsi,
                    flag       = EXCLUDED.flag,
                    vessel_type = EXCLUDED.vessel_type,
                    remarks    = EXCLUDED.remarks,
                    updated_at = EXCLUDED.updated_at
                """,
                [(s, n, p, i, m, f, v, r, datetime.now(timezone.utc))
                 for s, n, p, i, m, f, v, r in rows],
            )
            conn.commit()
            logger.info("EU sanctions: upserted %d vessel entries", len(rows))
            return len(rows)
    finally:
        conn.close()


def _extract_field(remarks: str, field: str) -> str | None:
    """Extract a field value like 'IMO 1234567' from OFAC remarks string."""
    for part in remarks.replace(";", " ").split():
        pass  # simple split won't work, need to find the pattern

    # Pattern: "IMO 1234567" or "MMSI 123456789"
    import re
    match = re.search(rf"{field}\s+(\d+)", remarks, re.IGNORECASE)
    return match.group(1) if match else None
