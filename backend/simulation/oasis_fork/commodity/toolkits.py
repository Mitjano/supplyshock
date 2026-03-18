"""Commodity market tools for OASIS agents.

All functions have complete docstrings with Args and Returns sections.

Data sources (priority order):
1. TimescaleDB (live) — commodity_prices, chokepoint_status, alert_events, trade_flows
2. Baseline fallback — hardcoded reference values when DB unavailable

The DB connection is injected via init_live_data(db_url). If not called,
all functions return baseline data (safe for POC/testing).
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Database connection (lazy, optional) ─────────────────────
_db_conn = None  # psycopg2 sync connection (Celery workers are sync)


def init_live_data(db_url: str) -> bool:
    """Initialize connection to TimescaleDB for live market data.

    Call this once before simulation starts. If not called or if connection
    fails, all toolkit functions fall back to baseline data.

    Args:
        db_url: PostgreSQL connection string (sync, not asyncpg).
            Example: 'postgresql://supplyshock:pass@db:5432/supplyshock'

    Returns:
        True if connected successfully, False otherwise.
    """
    global _db_conn
    try:
        import psycopg2
        _db_conn = psycopg2.connect(db_url)
        _db_conn.autocommit = True
        logger.info("Live data connected: %s", db_url.split("@")[-1])
        return True
    except Exception as e:
        logger.warning("Live data unavailable, using baseline: %s", e)
        _db_conn = None
        return False


def close_live_data() -> None:
    """Close TimescaleDB connection."""
    global _db_conn
    if _db_conn:
        try:
            _db_conn.close()
        except Exception:
            pass
        _db_conn = None


def _query(sql: str, params: tuple = ()) -> Optional[list]:
    """Execute query against TimescaleDB. Returns None if no connection."""
    if _db_conn is None:
        return None
    try:
        with _db_conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    except Exception as e:
        logger.warning("DB query failed (falling back to baseline): %s", e)
        return None


# ── Baseline data (fallback when DB unavailable) ─────────────

_BASELINE_PRICES: dict[str, dict[str, Any]] = {
    "coal": {"price_usd": 118.40, "unit": "tonne", "benchmark": "API2_Newcastle"},
    "crude_oil": {"price_usd": 74.20, "unit": "barrel", "benchmark": "Brent_ICE"},
    "lng": {"price_usd": 12.80, "unit": "mmbtu", "benchmark": "TTF_Europe"},
    "iron_ore": {"price_usd": 103.50, "unit": "tonne", "benchmark": "TSI_62pct_CFR"},
    "copper": {"price_usd": 9240.0, "unit": "tonne", "benchmark": "LME_Copper"},
    "wheat": {"price_usd": 192.00, "unit": "tonne", "benchmark": "CBOT_Wheat"},
    "aluminium": {"price_usd": 2380.0, "unit": "tonne", "benchmark": "LME_Aluminium"},
    "nickel": {"price_usd": 16200.0, "unit": "tonne", "benchmark": "LME_Nickel"},
    "soybeans": {"price_usd": 385.0, "unit": "tonne", "benchmark": "CBOT_Soybeans"},
    "palladium": {"price_usd": 1050.0, "unit": "troy_oz", "benchmark": "NYMEX_Palladium"},
}

_BASELINE_PORTS: dict[str, dict[str, Any]] = {
    "port_newcastle_au": {
        "vessel_count": 47, "congestion_index": 9.2,
        "risk_level": "critical", "disruption_active": True,
    },
    "port_richards_bay_za": {
        "vessel_count": 12, "congestion_index": 2.1,
        "risk_level": "normal", "disruption_active": False,
    },
    "strait_hormuz": {
        "vessel_count": 234, "congestion_index": 3.5,
        "risk_level": "elevated", "disruption_active": False,
    },
    "suez_canal": {
        "vessel_count": 89, "congestion_index": 4.1,
        "risk_level": "elevated", "disruption_active": False,
    },
    "port_kalimantan_id": {
        "vessel_count": 28, "congestion_index": 3.8,
        "risk_level": "normal", "disruption_active": False,
    },
}


# ── Tool functions ───────────────────────────────────────────

def get_commodity_price(commodity: str) -> dict:
    """Get current spot price for a commodity from market data.

    Reads latest price from TimescaleDB commodity_prices table.
    Falls back to baseline reference values if database unavailable.

    Args:
        commodity: Commodity identifier. One of: coal, crude_oil, lng,
            iron_ore, copper, wheat, aluminium, nickel, soybeans, palladium.

    Returns:
        dict: Contains keys: price_usd (float), unit (str), benchmark (str),
            change_1d_pct (float), source (str), is_live (bool).
            Returns error key if commodity not found.
    """
    # Try live data from TimescaleDB
    rows = _query(
        """
        SELECT benchmark, price, unit, source, time,
               LAG(price) OVER (ORDER BY time DESC) as prev_price
        FROM commodity_prices
        WHERE commodity = %s
        ORDER BY time DESC
        LIMIT 2
        """,
        (commodity,),
    )
    if rows and len(rows) >= 1:
        benchmark, price, unit, source, ts, prev_price = rows[0]
        change_pct = 0.0
        if prev_price and prev_price > 0:
            change_pct = round((float(price) - float(prev_price)) / float(prev_price) * 100, 2)
        return {
            "price_usd": float(price),
            "unit": unit,
            "benchmark": benchmark,
            "source": source,
            "change_1d_pct": change_pct,
            "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
            "is_live": True,
        }

    # Fallback to baseline
    if commodity not in _BASELINE_PRICES:
        return {
            "error": f"Unknown commodity: {commodity}. "
            f"Valid: {list(_BASELINE_PRICES.keys())}",
        }
    data = dict(_BASELINE_PRICES[commodity])
    data["change_1d_pct"] = 0.0
    data["source"] = "baseline"
    data["is_live"] = False
    return data


def get_port_congestion(port_slug: str) -> dict:
    """Get current vessel congestion at a port or maritime chokepoint.

    Reads latest status from TimescaleDB chokepoint_status + bottleneck_nodes.
    Falls back to baseline values if database unavailable.

    Args:
        port_slug: Port or chokepoint identifier. Examples:
            'port_newcastle_au', 'port_richards_bay_za', 'strait_hormuz',
            'suez_canal', 'port_kalimantan_id', 'strait_malacca'.

    Returns:
        dict: Contains keys: vessel_count (int), congestion_index (float, 0-10),
            risk_level (str: normal/elevated/high/critical),
            disruption_active (bool), is_live (bool).
    """
    # Try live data from TimescaleDB
    rows = _query(
        """
        SELECT cs.vessel_count, cs.congestion_index, cs.risk_level,
               cs.avg_speed_knots, cs.time,
               bn.name, bn.commodities
        FROM chokepoint_status cs
        JOIN bottleneck_nodes bn ON bn.id = cs.node_id
        WHERE bn.slug = %s
        ORDER BY cs.time DESC
        LIMIT 1
        """,
        (port_slug,),
    )
    if rows:
        vessel_count, congestion_idx, risk_level, avg_speed, ts, name, commodities = rows[0]
        # Disruption = critical or high risk
        disruption_active = risk_level in ("critical", "high")
        return {
            "name": name,
            "vessel_count": int(vessel_count),
            "congestion_index": float(congestion_idx) if congestion_idx else 0.0,
            "risk_level": risk_level,
            "avg_speed_knots": float(avg_speed) if avg_speed else None,
            "disruption_active": disruption_active,
            "commodities": commodities or [],
            "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
            "is_live": True,
        }

    # Fallback to baseline
    if port_slug not in _BASELINE_PORTS:
        return {
            "vessel_count": 0, "congestion_index": 0.0,
            "risk_level": "unknown", "disruption_active": False,
            "is_live": False,
            "note": f"No data for {port_slug}",
        }
    data = dict(_BASELINE_PORTS[port_slug])
    data["is_live"] = False
    return data


def get_trade_flow(commodity: str, origin: str, destination: str) -> dict:
    """Get monthly trade flow volume between two regions for a commodity.

    Reads from TimescaleDB trade_flows table. Falls back to reference data
    if database unavailable.

    Args:
        commodity: Commodity type (coal, crude_oil, lng, iron_ore, etc.)
        origin: Exporting country ISO code (e.g. 'AU', 'SA', 'RU', 'ID', 'US')
        destination: Importing country ISO code (e.g. 'JP', 'CN', 'DE', 'KR')

    Returns:
        dict: Contains keys: volume_mt_monthly (float), value_usd_monthly (float),
            alternative_sources (list of country codes), dependency_pct (float),
            is_live (bool).
    """
    # Try live data from TimescaleDB
    rows = _query(
        """
        SELECT volume_mt, value_usd, year
        FROM trade_flows
        WHERE commodity = %s AND origin_country = %s AND destination_country = %s
        ORDER BY year DESC
        LIMIT 1
        """,
        (commodity, origin, destination),
    )
    if rows:
        volume_mt, value_usd, year = rows[0]
        # Monthly estimate from annual
        monthly_volume = float(volume_mt) / 12 if volume_mt else 0
        monthly_value = float(value_usd) / 12 if value_usd else 0

        # Find alternative sources
        alt_rows = _query(
            """
            SELECT DISTINCT origin_country
            FROM trade_flows
            WHERE commodity = %s AND destination_country = %s
              AND origin_country != %s AND volume_mt > 0
            ORDER BY volume_mt DESC
            LIMIT 5
            """,
            (commodity, destination, origin),
        ) or []
        alternatives = [r[0] for r in alt_rows]

        # Calculate dependency %
        total_rows = _query(
            """
            SELECT SUM(volume_mt)
            FROM trade_flows
            WHERE commodity = %s AND destination_country = %s AND year = %s
            """,
            (commodity, destination, year),
        )
        total = float(total_rows[0][0]) if total_rows and total_rows[0][0] else 0
        dep_pct = round(float(volume_mt) / total, 3) if total > 0 else 0

        return {
            "volume_mt_monthly": round(monthly_volume),
            "value_usd_monthly": round(monthly_value),
            "alternative_sources": alternatives,
            "dependency_pct": dep_pct,
            "data_year": year,
            "is_live": True,
        }

    # Fallback to hardcoded reference flows
    _REFERENCE_FLOWS = {
        ("coal", "AU", "JP"): {
            "volume_mt_monthly": 3_200_000, "value_usd_monthly": 378_880_000,
            "alternative_sources": ["ZA", "CO", "ID"], "dependency_pct": 0.38,
        },
        ("coal", "AU", "CN"): {
            "volume_mt_monthly": 5_100_000, "value_usd_monthly": 603_840_000,
            "alternative_sources": ["ID", "MN", "RU"], "dependency_pct": 0.18,
        },
        ("coal", "AU", "KR"): {
            "volume_mt_monthly": 2_400_000, "value_usd_monthly": 284_160_000,
            "alternative_sources": ["ID", "ZA", "RU"], "dependency_pct": 0.32,
        },
        ("coal", "AU", "DE"): {
            "volume_mt_monthly": 800_000, "value_usd_monthly": 94_720_000,
            "alternative_sources": ["ZA", "CO", "US"], "dependency_pct": 0.15,
        },
        ("crude_oil", "SA", "JP"): {
            "volume_mt_monthly": 4_800_000, "value_usd_monthly": 1_751_040_000,
            "alternative_sources": ["AE", "KW", "IQ"], "dependency_pct": 0.42,
        },
    }
    key = (commodity, origin, destination)
    result = _REFERENCE_FLOWS.get(key, {
        "volume_mt_monthly": 0, "value_usd_monthly": 0,
        "alternative_sources": [], "dependency_pct": 0.0,
        "note": f"No flow data for {commodity} {origin}->{destination}",
    })
    result = dict(result)
    result["is_live"] = False
    return result


def get_recent_alerts(commodity: str, hours: int = 24) -> dict:
    """Get recent market alerts and news events for a commodity.

    Reads from TimescaleDB alert_events table (GDELT news + AIS anomalies).

    Args:
        commodity: Commodity to filter alerts for (coal, crude_oil, etc.)
        hours: How many hours back to look (default 24).

    Returns:
        dict: Contains keys: alerts (list of alert dicts), count (int),
            is_live (bool). Each alert has: severity, title, source, time.
    """
    rows = _query(
        """
        SELECT severity, title, body, source, time, type, region
        FROM alert_events
        WHERE (commodity = %s OR commodity IS NULL)
          AND time > NOW() - make_interval(hours => %s)
          AND is_active = TRUE
        ORDER BY
            CASE severity
                WHEN 'critical' THEN 1
                WHEN 'warning' THEN 2
                ELSE 3
            END,
            time DESC
        LIMIT 20
        """,
        (commodity, hours),
    )
    if rows:
        alerts = [
            {
                "severity": r[0],
                "title": r[1],
                "body": (r[2] or "")[:300],
                "source": r[3],
                "time": r[4].isoformat() if hasattr(r[4], "isoformat") else str(r[4]),
                "type": r[5],
                "region": r[6],
            }
            for r in rows
        ]
        return {"alerts": alerts, "count": len(alerts), "is_live": True}

    return {"alerts": [], "count": 0, "is_live": False}


def get_current_simulation_step() -> dict:
    """Get current simulation timestep and simulated date.

    Returns:
        dict: Contains keys: timestep (int), simulated_date (str ISO format),
            days_since_event (int, days since seed disruption event).
    """
    sim_step = int(os.environ.get("OASIS_SIM_STEP", "0"))
    return {
        "timestep": sim_step,
        "simulated_date": f"T+{sim_step * 7} days",
        "days_since_event": sim_step * 7,
    }


# ── Tool description strings for LLM agents ─────────────────

TOOL_DESCRIPTIONS = """Available market data tools:
- get_commodity_price(commodity) → current spot price, benchmark, daily change %
- get_port_congestion(port_slug) → vessel count, congestion index 0-10, risk level
- get_trade_flow(commodity, origin, destination) → monthly volume, value, alternatives, dependency %
- get_recent_alerts(commodity, hours) → recent news events and anomalies by severity
- get_current_simulation_step() → current timestep, simulated date"""

# Ready-to-use tool lists
COMMODITY_TOOLS = [
    get_commodity_price,
    get_port_congestion,
    get_trade_flow,
    get_recent_alerts,
    get_current_simulation_step,
]

TRADER_TOOLS = COMMODITY_TOOLS

SHIPPER_TOOLS = [
    get_port_congestion,
    get_recent_alerts,
    get_current_simulation_step,
]

GOVERNMENT_TOOLS = COMMODITY_TOOLS
