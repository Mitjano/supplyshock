"""Commodity endpoints — /api/v1/commodities/*

- GET /commodities/prices             — latest prices
- GET /commodities/prices/{commodity}/history — price history
- GET /commodities/flows              — trade flows as GeoJSON
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from middleware.auth import require_auth

router = APIRouter(prefix="/commodities", tags=["Commodities"])


async def _get_db():
    from main import engine
    from sqlalchemy.ext.asyncio import async_sessionmaker

    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


@router.get("/prices")
async def get_latest_prices(
    commodities: str | None = Query(None, description="Comma-separated: crude_oil,coal,copper"),
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(_get_db),
):
    """Get latest commodity prices."""
    conditions = []
    params: dict[str, Any] = {}

    if commodities:
        commodity_list = [c.strip() for c in commodities.split(",")]
        conditions.append("commodity = ANY(:commodities)")
        params["commodities"] = commodity_list

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    result = await db.execute(
        text(f"""
            SELECT DISTINCT ON (commodity, benchmark)
                commodity, benchmark, price, currency, unit, source, time
            FROM commodity_prices
            {where}
            ORDER BY commodity, benchmark, time DESC
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
        ]
    }


@router.get("/prices/{commodity}/history")
async def get_price_history(
    commodity: str,
    days: int = Query(30, le=365),
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(_get_db),
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
    limit: int = Query(20, le=100),
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(_get_db),
):
    """Get trade flows as GeoJSON FeatureCollection.

    Each feature is a LineString between origin and destination ports,
    with properties: origin, destination, volume_mt, value_usd, commodity.
    """
    conditions = []
    params: dict[str, Any] = {"limit": limit}

    if commodity:
        conditions.append("tf.commodity = :commodity")
        params["commodity"] = commodity

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    result = await db.execute(
        text(f"""
            SELECT tf.commodity, tf.origin_country, tf.destination_country,
                   tf.volume_mt, tf.value_usd,
                   op.latitude as origin_lat, op.longitude as origin_lng, op.name as origin_port,
                   dp.latitude as dest_lat, dp.longitude as dest_lng, dp.name as dest_port
            FROM trade_flows tf
            LEFT JOIN ports op ON op.country_code = tf.origin_country AND op.is_major = true
            LEFT JOIN ports dp ON dp.country_code = tf.destination_country AND dp.is_major = true
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
                },
            })

    return {
        "type": "FeatureCollection",
        "features": features,
    }
