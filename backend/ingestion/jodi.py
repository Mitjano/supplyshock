"""JODI Oil data ingestion via UN Data API.

Fetches JODI (Joint Organisations Data Initiative) oil supply/demand
balance data and stores in supply_demand_balance table.
Runs weekly via Celery Beat.

Issue #82
"""

import logging
from datetime import datetime, timezone

import httpx
import psycopg2
from psycopg2.extras import execute_values

from config import settings

logger = logging.getLogger(__name__)

# UN Data API endpoint for JODI Oil World Database
UNDATA_API_URL = "https://data.un.org/ws/rest/data/UNSD,DF_UNDATA_JODI,1.0"

# JODI flow codes → metric names
JODI_FLOWS = {
    "PRODTN": "production",
    "TOTDEM": "consumption",
    "CLOSTK": "ending_stocks",
    "IMPPRT": "imports",
    "EXPPRT": "exports",
    "TOTTRF": "transfers",
}

# Top oil-producing/consuming countries (ISO alpha-2)
DEFAULT_COUNTRIES = ["SA", "RU", "US", "CN", "IQ", "AE", "IR", "BR", "KW", "NO"]


def fetch_jodi_oil(countries: list[str] | None = None) -> list[dict]:
    """Fetch JODI oil data from UN Data API (SDMX JSON).

    Uses the free UN Data SDMX REST endpoint. No API key required.
    """
    target_countries = countries or DEFAULT_COUNTRIES
    records: list[dict] = []

    for country in target_countries:
        try:
            # SDMX key: FREQ.REF_AREA.ENERGY_PRODUCT.FLOW_BREAKDOWN.UNIT_MEASURE
            # OIL = OILCRD (crude oil)
            key = f"M.{country}.OILCRD.....Z"
            url = f"{UNDATA_API_URL}/{key}"

            resp = httpx.get(
                url,
                params={"format": "jsondata", "lastNObservations": 24},
                headers={"Accept": "application/json"},
                timeout=60,
            )

            if resp.status_code == 404:
                logger.debug("No JODI data for country %s", country)
                continue
            resp.raise_for_status()
            data = resp.json()

            # Parse SDMX JSON structure
            datasets = data.get("dataSets", [])
            if not datasets:
                continue

            structure = data.get("structure", {})
            dimensions = structure.get("dimensions", {}).get("observation", [])

            # Find time dimension
            time_dim = None
            for dim in dimensions:
                if dim.get("id") == "TIME_PERIOD":
                    time_dim = dim
                    break

            series_data = datasets[0].get("series", {})
            for series_key, series_val in series_data.items():
                key_parts = series_key.split(":")
                # Extract flow code from key
                flow_idx = None
                for i, dim in enumerate(structure.get("dimensions", {}).get("series", [])):
                    if dim.get("id") == "FLOW_BREAKDOWN":
                        flow_idx = i
                        break

                if flow_idx is not None and flow_idx < len(key_parts):
                    flow_code_idx = int(key_parts[flow_idx])
                    flow_dim = structure["dimensions"]["series"][flow_idx]
                    flow_values = flow_dim.get("values", [])
                    if flow_code_idx < len(flow_values):
                        flow_code = flow_values[flow_code_idx].get("id", "")
                    else:
                        continue
                else:
                    continue

                metric = JODI_FLOWS.get(flow_code)
                if not metric:
                    continue

                observations = series_val.get("observations", {})
                for obs_key, obs_val in observations.items():
                    value = obs_val[0] if obs_val else None
                    if value is None:
                        continue

                    # Get time period
                    if time_dim:
                        time_values = time_dim.get("values", [])
                        obs_idx = int(obs_key)
                        if obs_idx < len(time_values):
                            period = time_values[obs_idx].get("id", "")
                        else:
                            continue
                    else:
                        continue

                    records.append({
                        "commodity": "crude_oil",
                        "metric": metric,
                        "value": float(value),
                        "unit": "thousand_barrels_per_day",
                        "period": period,
                        "source": "jodi",
                        "country": country,
                    })

            logger.info("Fetched JODI data for %s: %d records", country, len([r for r in records if r["country"] == country]))

        except Exception as e:
            logger.error("JODI fetch failed for %s: %s", country, e)

    return records


def ingest_jodi_oil(countries: list[str] | None = None) -> int:
    """Fetch and store JODI oil supply/demand balance data."""
    records = fetch_jodi_oil(countries)
    if not records:
        logger.info("No JODI records to ingest")
        return 0

    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        with conn.cursor() as cur:
            # Ensure source column supports 'jodi' — table already exists (Issue #70)
            values = [
                (r["commodity"], r["metric"], r["value"], r["unit"], r["period"], r["source"])
                for r in records
            ]
            execute_values(
                cur,
                """
                INSERT INTO supply_demand_balance (commodity, metric, value, unit, period, source)
                VALUES %s
                ON CONFLICT (commodity, metric, period, source)
                DO UPDATE SET
                    value = EXCLUDED.value,
                    unit = EXCLUDED.unit
                """,
                values,
            )
        conn.commit()
        logger.info("Ingested %d JODI oil records", len(records))
    finally:
        conn.close()

    return len(records)
