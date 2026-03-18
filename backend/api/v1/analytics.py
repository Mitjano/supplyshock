"""Analytics endpoints — /api/v1/analytics/*

- GET /analytics/emissions          — total emissions per commodity route
- GET /analytics/price-bands        — Issue #60
- GET /analytics/cot                — CFTC COT positioning (Issue #64)
- GET /analytics/inventories        — EIA inventory data (Issue #65)
- GET /analytics/cracks             — Crack spread data (Issue #66)
- GET /analytics/correlations       — Commodity correlation matrix (Issue #67)
- GET /analytics/seasonal           — Seasonal price patterns (Issue #68)
- GET /analytics/forward-curve      — Forward/futures curve (Issue #69)
- GET /analytics/balance/{commodity} — Supply/demand balance (Issue #70, #82)
- GET /analytics/rigs               — Baker Hughes rig counts (Issue #81)
- GET /analytics/inventories/natgas — EIA natural gas storage (Issue #83)
- GET /analytics/spr                — Strategic Petroleum Reserve (Issue #83)
- GET /analytics/bunker             — Bunker fuel proxy prices (Issue #87)
- GET /analytics/warehouse          — Metal warehouse stock proxies (Issue #90)
"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from analytics.correlations import get_correlations_cached
from analytics.emissions import estimate_voyage_emissions, FUEL_CONSUMPTION
from analytics.price_anomaly import get_price_bands as _get_price_bands
from analytics.seasonal import compute_seasonal_pattern
from dependencies import get_db, get_redis
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/emissions")
async def get_emissions_by_commodity(
    commodity: str | None = Query(None, description="Filter by cargo commodity (e.g. crude_oil, lng, coal)"),
    period: str = Query("30d", description="Time period: 7d, 30d, 90d"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Total estimated emissions per commodity route for completed/underway voyages."""
    interval_map = {"7d": "7 days", "30d": "30 days", "90d": "90 days"}
    interval = interval_map.get(period, "30 days")

    conditions = [f"v.departure_time > NOW() - INTERVAL '{interval}'"]
    conditions.append("v.distance_nm IS NOT NULL")
    conditions.append("v.distance_nm > 0")
    params: dict[str, Any] = {}

    if commodity:
        conditions.append("v.cargo_type = :commodity")
        params["commodity"] = commodity

    where = f"WHERE {' AND '.join(conditions)}"

    result = await db.execute(
        text(f"""
            SELECT v.cargo_type,
                   v.vessel_type,
                   COUNT(*) as voyage_count,
                   SUM(v.distance_nm) as total_distance_nm,
                   AVG(v.distance_nm) as avg_distance_nm,
                   SUM(v.volume_estimate) as total_volume
            FROM voyages v
            {where}
            GROUP BY v.cargo_type, v.vessel_type
            ORDER BY v.cargo_type, voyage_count DESC
        """),
        params,
    )
    rows = result.mappings().all()

    emissions_data = []
    total_co2 = 0.0
    total_fuel = 0.0

    for r in rows:
        avg_dist = float(r["avg_distance_nm"]) if r["avg_distance_nm"] else 0
        voyage_count = r["voyage_count"]
        vessel_type = r["vessel_type"] or "default"

        # Map vessel_type enum to fuel consumption key
        fuel_key = _map_vessel_type(vessel_type)
        avg_speed = 12.0  # Reasonable average for laden commodity vessels
        avg_dwt = 150000.0  # Default estimate

        # Estimate per-voyage emissions at average distance
        est = estimate_voyage_emissions(avg_dist, fuel_key, avg_speed, avg_dwt)
        route_co2 = est["co2_estimate_tonnes"] * voyage_count
        route_fuel = est["fuel_estimate_tonnes"] * voyage_count
        total_co2 += route_co2
        total_fuel += route_fuel

        emissions_data.append({
            "cargo_type": r["cargo_type"],
            "vessel_type": r["vessel_type"],
            "voyage_count": voyage_count,
            "total_distance_nm": float(r["total_distance_nm"]) if r["total_distance_nm"] else 0,
            "avg_distance_nm": round(avg_dist, 1),
            "total_volume_estimate": float(r["total_volume"]) if r["total_volume"] else None,
            "estimated_co2_tonnes": round(route_co2, 2),
            "estimated_fuel_tonnes": round(route_fuel, 2),
            "avg_cii_rating": est["cii_rating"],
        })

    return {
        "data": emissions_data,
        "summary": {
            "period": period,
            "total_co2_tonnes": round(total_co2, 2),
            "total_fuel_tonnes": round(total_fuel, 2),
        },
    }


@router.get("/price-bands")
async def get_price_bands(
    commodity: str = Query(..., description="Commodity: crude_oil, lng, coal, iron_ore, copper"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Statistical price bands for a commodity (Bollinger-style).

    Returns 30-day rolling mean/std, 1σ and 2σ bands, current price,
    percentile rank (vs 90-day history), and a daily time series of bands
    for chart overlay.
    """
    data = await _get_price_bands(db, commodity)
    return {"data": data}


# ── Issue #64 — CFTC COT ──

@router.get("/cot")
async def get_cot_reports(
    commodity: str = Query(..., description="Commodity: crude_oil, natural_gas, gold, silver, copper, wheat, corn, soybeans"),
    weeks: int = Query(52, ge=1, le=260, description="Number of weeks of history"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """CFTC Commitments of Traders positioning data."""
    result = await db.execute(
        text("""
            SELECT report_date, open_interest,
                   commercial_net, non_commercial_net, managed_money_net
            FROM cot_reports
            WHERE commodity = :commodity
            ORDER BY report_date DESC
            LIMIT :weeks
        """),
        {"commodity": commodity, "weeks": weeks},
    )
    rows = result.mappings().all()
    return {
        "data": [
            {
                "report_date": str(r["report_date"]),
                "open_interest": r["open_interest"],
                "commercial_net": r["commercial_net"],
                "non_commercial_net": r["non_commercial_net"],
                "managed_money_net": r["managed_money_net"],
            }
            for r in rows
        ],
        "commodity": commodity,
        "weeks": weeks,
    }


# ── Issue #65 — EIA Inventories ──

@router.get("/inventories")
async def get_inventories(
    series: str = Query(..., description="Series: crude_stocks, gasoline_stocks, distillate_stocks, refinery_utilization, cushing_stocks"),
    weeks: int = Query(52, ge=1, le=260, description="Number of weeks of history"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """EIA weekly petroleum inventory data."""
    result = await db.execute(
        text("""
            SELECT time, value, unit
            FROM eia_inventories
            WHERE series = :series
            ORDER BY time DESC
            LIMIT :weeks
        """),
        {"series": series, "weeks": weeks},
    )
    rows = result.mappings().all()
    return {
        "data": [
            {
                "time": r["time"].isoformat() if hasattr(r["time"], "isoformat") else str(r["time"]),
                "value": r["value"],
                "unit": r["unit"],
            }
            for r in rows
        ],
        "series": series,
        "weeks": weeks,
    }


# ── Issue #66 — Crack Spreads ──

@router.get("/cracks")
async def get_crack_spreads(
    days: int = Query(90, ge=1, le=365, description="Number of days of history"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """3-2-1 crack spread history."""
    # days is already validated as int (1-365) by Query, safe to interpolate
    result = await db.execute(
        text(f"""
            SELECT time, spread_type, wti_price, gasoline_price,
                   heating_oil_price, spread_value
            FROM crack_spreads
            WHERE time >= NOW() - INTERVAL '{days} days'
            ORDER BY time DESC
        """),
    )
    rows = result.mappings().all()
    return {
        "data": [
            {
                "time": r["time"].isoformat() if hasattr(r["time"], "isoformat") else str(r["time"]),
                "spread_type": r["spread_type"],
                "wti": float(r["wti_price"]),
                "gasoline_per_bbl": float(r["gasoline_price"]),
                "heating_oil_per_bbl": float(r["heating_oil_price"]),
                "spread": float(r["spread_value"]),
            }
            for r in rows
        ],
        "days": days,
    }


# ── Issue #67 — Correlation Matrix ──

@router.get("/correlations")
async def get_correlations(
    window: str = Query("30d", description="Window: 7d, 30d, 90d"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Pearson correlation matrix of commodity daily returns."""
    from dependencies import get_redis as _get_redis
    redis_client = await _get_redis()
    data = await get_correlations_cached(db, redis_client, window)
    return {"data": data}


# ── Issue #68 — Seasonal Patterns ──

@router.get("/seasonal")
async def get_seasonal(
    commodity: str = Query(..., description="Commodity: crude_oil, lng, gold, etc."),
    years: int = Query(5, ge=2, le=20, description="Number of historical years"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Seasonal price patterns (day-of-year indexed to Jan 1 = 100)."""
    data = await compute_seasonal_pattern(db, commodity, years)
    return {"data": data}


# ── Issue #69 — Forward Curves ──

@router.get("/forward-curve")
async def get_forward_curve(
    commodity: str = Query(..., description="Commodity: crude_oil, natural_gas, gold"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Forward/futures curve for a commodity.

    Returns the latest set of contract months with settlement prices
    and identifies curve structure (contango, backwardation, or flat).
    """
    result = await db.execute(
        text("""
            WITH latest AS (
                SELECT MAX(time) as max_time
                FROM forward_curves
                WHERE commodity = :commodity
            )
            SELECT fc.contract_month, fc.expiry_date, fc.settlement_price, fc.time
            FROM forward_curves fc
            JOIN latest l ON fc.time = l.max_time
            WHERE fc.commodity = :commodity
            ORDER BY fc.expiry_date ASC
        """),
        {"commodity": commodity},
    )
    rows = result.mappings().all()

    if not rows:
        return {"data": [], "structure": "unknown", "commodity": commodity}

    contracts = [
        {
            "contract_month": r["contract_month"],
            "expiry_date": r["expiry_date"].isoformat() if hasattr(r["expiry_date"], "isoformat") else str(r["expiry_date"]),
            "settlement_price": float(r["settlement_price"]),
        }
        for r in rows
    ]

    # Determine curve structure
    prices = [c["settlement_price"] for c in contracts]
    if len(prices) >= 2:
        front = prices[0]
        back = prices[-1]
        spread_pct = (back - front) / front * 100 if front > 0 else 0
        if spread_pct > 1.0:
            structure = "contango"
        elif spread_pct < -1.0:
            structure = "backwardation"
        else:
            structure = "flat"
    else:
        structure = "unknown"
        spread_pct = 0

    return {
        "data": contracts,
        "commodity": commodity,
        "structure": structure,
        "front_back_spread_pct": round(spread_pct, 2),
        "snapshot_time": str(rows[0]["time"]) if rows else None,
    }


# ── Issue #70 — Supply/Demand Balance ──

@router.get("/balance/{commodity}")
async def get_supply_demand_balance(
    commodity: str,
    source: str | None = Query(None, description="Filter by source: eia_steo, usda_wasde, jodi (Issue #82)"),
    countries: str | None = Query(None, description="Comma-separated ISO alpha-2 country codes for JODI (e.g. SA,RU)"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Supply/demand balance for a commodity.

    Returns production, consumption, stock changes, and ending stocks
    from EIA STEO (energy), USDA WASDE (agriculture), or JODI (Issue #82) data.
    Use ?source=jodi&countries=SA,RU to filter JODI data by country.
    """
    conditions = ["commodity = :commodity"]
    params: dict[str, Any] = {"commodity": commodity}

    if source:
        conditions.append("source = :source")
        params["source"] = source

    where = " AND ".join(conditions)

    result = await db.execute(
        text(f"""
            SELECT metric, value, unit, period, source
            FROM supply_demand_balance
            WHERE {where}
            ORDER BY period DESC, metric ASC
        """),
        params,
    )
    rows = result.mappings().all()

    if not rows:
        return {"data": {}, "commodity": commodity, "message": "No balance data available"}

    # Group by period
    periods: dict[str, dict] = {}
    for r in rows:
        period = r["period"]
        if period not in periods:
            periods[period] = {"period": period, "source": r["source"]}
        periods[period][r["metric"]] = {
            "value": float(r["value"]),
            "unit": r["unit"],
        }

    # Calculate implied stock change where we have production + consumption
    for p_data in periods.values():
        prod = p_data.get("production", {}).get("value")
        cons = p_data.get("consumption", {}).get("value")
        if prod is not None and cons is not None:
            p_data["stock_change"] = {
                "value": round(prod - cons, 3),
                "unit": p_data.get("production", {}).get("unit", ""),
            }

    sorted_periods = sorted(periods.values(), key=lambda x: x["period"], reverse=True)

    return {
        "data": sorted_periods,
        "commodity": commodity,
        "periods_count": len(sorted_periods),
    }


# ── Issue #81 — Baker Hughes Rig Counts ──

@router.get("/rigs")
async def get_rig_counts(
    region: str = Query("US", description="Region: US"),
    type: str = Query("oil", description="Rig type: oil, gas, total, misc"),
    weeks: int = Query(52, ge=1, le=520, description="Number of weeks of history"),
    basin: str = Query(None, description="Basin filter: permian, eagle_ford, bakken, etc."),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Baker Hughes rig count data via EIA.

    Returns weekly rig counts by type (oil/gas/total) with change statistics.
    """
    conditions = ["region = :region", "rig_type = :rig_type"]
    params: dict[str, Any] = {"region": region, "rig_type": type, "weeks": weeks}

    if basin:
        conditions.append("basin = :basin")
        params["basin"] = basin

    where = " AND ".join(conditions)

    result = await db.execute(
        text(f"""
            SELECT report_date, count, basin
            FROM rig_counts
            WHERE {where}
            ORDER BY report_date DESC
            LIMIT :weeks
        """),
        params,
    )
    rows = result.mappings().all()

    data = [
        {
            "date": str(r["report_date"]),
            "count": r["count"],
            "basin": r["basin"],
        }
        for r in rows
    ]

    # Calculate week-over-week and year-over-year changes
    summary: dict[str, Any] = {"region": region, "type": type, "weeks": weeks}
    if len(data) >= 2:
        summary["current"] = data[0]["count"]
        summary["wow_change"] = data[0]["count"] - data[1]["count"]
    if len(data) >= 52:
        summary["yoy_change"] = data[0]["count"] - data[51]["count"]

    return {"data": data, "summary": summary}


# ── Issue #83 — Natural Gas Storage ──

@router.get("/inventories/natgas")
async def get_natgas_storage(
    weeks: int = Query(52, ge=1, le=260, description="Number of weeks of history"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """EIA natural gas working storage data."""
    result = await db.execute(
        text("""
            SELECT time, value, unit
            FROM eia_inventories
            WHERE series = 'natgas_storage'
            ORDER BY time DESC
            LIMIT :weeks
        """),
        {"weeks": weeks},
    )
    rows = result.mappings().all()
    return {
        "data": [
            {
                "time": r["time"].isoformat() if hasattr(r["time"], "isoformat") else str(r["time"]),
                "value": r["value"],
                "unit": r["unit"],
            }
            for r in rows
        ],
        "series": "natgas_storage",
        "weeks": weeks,
    }


# ── Issue #83 — Strategic Petroleum Reserve ──

@router.get("/spr")
async def get_spr(
    weeks: int = Query(52, ge=1, le=260, description="Number of weeks of history"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """US Strategic Petroleum Reserve stock levels."""
    result = await db.execute(
        text("""
            SELECT time, value, unit
            FROM eia_inventories
            WHERE series = 'spr_stocks'
            ORDER BY time DESC
            LIMIT :weeks
        """),
        {"weeks": weeks},
    )
    rows = result.mappings().all()
    return {
        "data": [
            {
                "time": r["time"].isoformat() if hasattr(r["time"], "isoformat") else str(r["time"]),
                "value": r["value"],
                "unit": r["unit"],
            }
            for r in rows
        ],
        "series": "spr_stocks",
        "weeks": weeks,
    }


# ── Issue #87 — Bunker Fuel Proxy Prices ──

@router.get("/bunker")
async def get_bunker_prices(
    fuel: str = Query("vlsfo_proxy", description="Fuel type: vlsfo_proxy, mgo_proxy"),
    days: int = Query(30, ge=1, le=365, description="Number of days of history"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Bunker fuel proxy prices (heating oil → VLSFO, diesel → MGO)."""
    result = await db.execute(
        text(f"""
            SELECT time, fuel_type, price_per_mt, price_per_bbl, source_ticker
            FROM bunker_prices
            WHERE fuel_type = :fuel
              AND time >= NOW() - INTERVAL '{days} days'
            ORDER BY time DESC
        """),
        {"fuel": fuel},
    )
    rows = result.mappings().all()
    return {
        "data": [
            {
                "time": r["time"].isoformat() if hasattr(r["time"], "isoformat") else str(r["time"]),
                "fuel_type": r["fuel_type"],
                "price_per_mt": r["price_per_mt"],
                "price_per_bbl": r["price_per_bbl"],
                "source_ticker": r["source_ticker"],
            }
            for r in rows
        ],
        "fuel": fuel,
        "days": days,
    }


# ── Issue #90 — Metal Warehouse Stocks ──

@router.get("/warehouse")
async def get_warehouse_stocks(
    metal: str = Query("copper", description="Metal: copper, industrial_metals, silver, gold"),
    days: int = Query(90, ge=1, le=365, description="Number of days of history"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Metal warehouse stock proxy data (ETF-based)."""
    result = await db.execute(
        text(f"""
            SELECT time, metal, etf_ticker, price, volume
            FROM warehouse_stocks
            WHERE metal = :metal
              AND time >= NOW() - INTERVAL '{days} days'
            ORDER BY time DESC
        """),
        {"metal": metal},
    )
    rows = result.mappings().all()
    return {
        "data": [
            {
                "time": r["time"].isoformat() if hasattr(r["time"], "isoformat") else str(r["time"]),
                "metal": r["metal"],
                "etf_ticker": r["etf_ticker"],
                "price": r["price"],
                "volume": r["volume"],
            }
            for r in rows
        ],
        "metal": metal,
        "days": days,
    }


def _map_vessel_type(vessel_type: str) -> str:
    """Map database vessel_type enum to fuel consumption lookup key."""
    mapping = {
        "tanker": "tanker_vlcc",
        "tanker_vlcc": "tanker_vlcc",
        "tanker_suezmax": "tanker_suezmax",
        "tanker_aframax": "tanker_aframax",
        "bulk_carrier": "bulk_capesize",
        "bulk_capesize": "bulk_capesize",
        "bulk_panamax": "bulk_panamax",
        "container": "container_large",
        "container_large": "container_large",
        "lng_carrier": "lng_carrier",
    }
    return mapping.get(vessel_type, "default")
