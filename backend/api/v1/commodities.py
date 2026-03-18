"""Commodity endpoints — /api/v1/commodities/*

- GET /commodities/prices             — latest prices
- GET /commodities/prices/{commodity}/history — price history
- GET /commodities/flows              — trade flows as GeoJSON
- GET /commodities/flows/{commodity}/trend — supply trend analysis
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from analytics.supply_trend import get_supply_trend
from dependencies import get_db
from middleware.auth import require_auth
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/commodities", tags=["Commodities"])


@router.get("/prices")
async def get_latest_prices(
    commodities: str | None = Query(None, description="Comma-separated: crude_oil,coal,copper"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Get latest commodity prices."""
    conditions = []
    params: dict[str, Any] = {"limit": limit, "offset": offset}

    if commodities:
        commodity_list = [c.strip() for c in commodities.split(",")]
        conditions.append("commodity = ANY(:commodities)")
        params["commodities"] = commodity_list

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # Get total count of distinct commodity/benchmark pairs
    count_result = await db.execute(
        text(f"""
            SELECT COUNT(*) FROM (
                SELECT DISTINCT commodity, benchmark FROM commodity_prices
                {where}
            ) sub
        """),
        params,
    )
    total = count_result.scalar()

    result = await db.execute(
        text(f"""
            SELECT DISTINCT ON (commodity, benchmark)
                commodity, benchmark, price, currency, unit, source, time
            FROM commodity_prices
            {where}
            ORDER BY commodity, benchmark, time DESC
            LIMIT :limit OFFSET :offset
        """),
        params,
    )
    rows = result.mappings().all()

    return {
        "data": [
            {
                "commodity": row["commodity"],
                "benchmark": row["benchmark"],
                "price": float(row["price"]),
                "currency": row["currency"],
                "unit": row["unit"],
                "source": row["source"],
                "time": row["time"].isoformat(),
            }
            for row in rows
        ],
        "meta": {"total": total, "offset": offset, "limit": limit},
    }


@router.get("/prices/{commodity}/history")
async def get_price_history(
    commodity: str,
    days: int = Query(30, le=365),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Get price history for a specific commodity."""
    result = await db.execute(
        text("""
            SELECT commodity, benchmark, price, currency, unit, source, time
            FROM commodity_prices
            WHERE commodity = :commodity
              AND time > NOW() - make_interval(days => :days)
            ORDER BY time ASC
        """),
        {"commodity": commodity, "days": days},
    )
    rows = result.mappings().all()

    return {
        "data": [
            {
                "commodity": row["commodity"],
                "benchmark": row["benchmark"],
                "price": float(row["price"]),
                "currency": row["currency"],
                "unit": row["unit"],
                "source": row["source"],
                "time": row["time"].isoformat(),
            }
            for row in rows
        ]
    }


@router.get("/flows")
async def get_trade_flows(
    commodity: str | None = Query(None),
    source: str | None = Query(None, description="Filter by source: 'un_comtrade', 'live', or None for all"),
    origin_country: str | None = Query(None, description="ISO 3166-1 alpha-2 origin country"),
    dest_country: str | None = Query(None, description="ISO 3166-1 alpha-2 destination country"),
    limit: int = Query(20, le=100),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Get trade flows as GeoJSON FeatureCollection.

    Each feature is a LineString between origin and destination ports,
    with properties: origin, destination, volume_mt, value_usd, commodity, source.

    source='live' returns flows enriched from real-time voyage data (#44).
    source='un_comtrade' returns static trade data.
    """
    conditions = []
    params: dict[str, Any] = {"limit": limit}

    if commodity:
        conditions.append("tf.commodity = :commodity")
        params["commodity"] = commodity

    if source:
        conditions.append("tf.source = :source")
        params["source"] = source

    if origin_country:
        conditions.append("tf.origin_country = :origin_country")
        params["origin_country"] = origin_country

    if dest_country:
        conditions.append("tf.destination_country = :dest_country")
        params["dest_country"] = dest_country

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    result = await db.execute(
        text(f"""
            SELECT tf.commodity, tf.origin_country, tf.destination_country,
                   tf.volume_mt, tf.value_usd, tf.source,
                   op.latitude as origin_lat, op.longitude as origin_lng, op.name as origin_port,
                   dp.latitude as dest_lat, dp.longitude as dest_lng, dp.name as dest_port
            FROM trade_flows tf
            LEFT JOIN ports op ON op.id = tf.origin_port_id
            LEFT JOIN ports dp ON dp.id = tf.destination_port_id
            {where}
            ORDER BY tf.volume_mt DESC NULLS LAST
            LIMIT :limit
        """),
        params,
    )
    rows = result.mappings().all()

    features = []
    for row in rows:
        if row["origin_lat"] and row["dest_lat"]:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [float(row["origin_lng"]), float(row["origin_lat"])],
                        [float(row["dest_lng"]), float(row["dest_lat"])],
                    ],
                },
                "properties": {
                    "commodity": row["commodity"],
                    "origin": row["origin_port"] or row["origin_country"],
                    "destination": row["dest_port"] or row["destination_country"],
                    "origin_country": row["origin_country"],
                    "destination_country": row["destination_country"],
                    "volume_mt": float(row["volume_mt"]) if row["volume_mt"] else None,
                    "value_usd": float(row["value_usd"]) if row["value_usd"] else None,
                    "source": row["source"],
                },
            })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


@router.get("/flows/{commodity}/trend")
async def get_commodity_trend(
    commodity: str,
    origin: str | None = Query(None, description="ISO 3166-1 alpha-2 origin country"),
    destination: str | None = Query(None, description="ISO 3166-1 alpha-2 destination country"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Get supply trend analysis for a commodity.

    Returns rolling volume averages (7d/30d/90d), trend direction
    (growing/declining/stable), and a 30-day volume prediction.
    """
    result = await get_supply_trend(db, commodity, origin=origin, destination=destination)

    if result["data_points"] == 0:
        raise HTTPException(status_code=404, detail=f"No trade flow data found for '{commodity}'")

    return {"data": result}
