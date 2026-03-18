"""Supply trend analysis for trade flows.

Calculates rolling volume averages, trend direction, and simple
linear-regression-based 30-day predictions from the trade_flows table.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_supply_trend(
    db: AsyncSession,
    commodity: str,
    origin: str | None = None,
    destination: str | None = None,
) -> dict:
    """Analyse supply trend for a commodity based on trade_flows data.

    Returns rolling averages (7d/30d/90d), trend direction, and a 30-day
    volume prediction via simple linear regression on the last 30 days of
    daily aggregated volumes.
    """

    # --- build optional filters -------------------------------------------
    conditions = ["commodity = :commodity"]
    params: dict = {"commodity": commodity}

    if origin:
        conditions.append("origin_country = :origin")
        params["origin"] = origin

    if destination:
        conditions.append("dest_country = :destination")
        params["destination"] = destination

    where = " AND ".join(conditions)

    # --- rolling averages -------------------------------------------------
    avg_result = await db.execute(
        text(f"""
            SELECT
                COALESCE(SUM(volume_mt) FILTER (
                    WHERE updated_at > NOW() - INTERVAL '7 days'
                ), 0)  AS vol_7d,
                COALESCE(SUM(volume_mt) FILTER (
                    WHERE updated_at > NOW() - INTERVAL '30 days'
                ), 0)  AS vol_30d,
                COALESCE(SUM(volume_mt) FILTER (
                    WHERE updated_at > NOW() - INTERVAL '90 days'
                ), 0)  AS vol_90d
            FROM trade_flows
            WHERE {where}
              AND updated_at > NOW() - INTERVAL '90 days'
        """),
        params,
    )
    row = avg_result.mappings().one()
    vol_7d = float(row["vol_7d"])
    vol_30d = float(row["vol_30d"])
    vol_90d = float(row["vol_90d"])

    # --- trend direction --------------------------------------------------
    if vol_30d > 0 and vol_7d > vol_30d * (7 / 30) * 1.1:
        trend = "growing"
    elif vol_30d > 0 and vol_7d < vol_30d * (7 / 30) * 0.9:
        trend = "declining"
    else:
        trend = "stable"

    # --- linear regression on daily volumes (last 30d) --------------------
    daily_result = await db.execute(
        text(f"""
            SELECT
                updated_at::date AS day,
                SUM(volume_mt)   AS daily_vol
            FROM trade_flows
            WHERE {where}
              AND updated_at > NOW() - INTERVAL '30 days'
            GROUP BY day
            ORDER BY day
        """),
        params,
    )
    daily_rows = daily_result.mappings().all()
    data_points = len(daily_rows)

    prediction_30d: float | None = None
    if data_points >= 2:
        # simple linear regression: y = a + b*x, x = day index starting at 0
        xs = list(range(data_points))
        ys = [float(r["daily_vol"]) for r in daily_rows]

        n = data_points
        sum_x = sum(xs)
        sum_y = sum(ys)
        sum_xy = sum(x * y for x, y in zip(xs, ys))
        sum_x2 = sum(x * x for x in xs)

        denom = n * sum_x2 - sum_x * sum_x
        if denom != 0:
            b = (n * sum_xy - sum_x * sum_y) / denom
            a = (sum_y - b * sum_x) / n
            # predict total volume over next 30 days
            last_x = xs[-1]
            prediction_30d = sum(
                max(a + b * (last_x + d), 0) for d in range(1, 31)
            )

    return {
        "commodity": commodity,
        "trend": trend,
        "volume_7d": vol_7d,
        "volume_30d": vol_30d,
        "volume_90d": vol_90d,
        "prediction_30d": round(prediction_30d, 2) if prediction_30d is not None else None,
        "data_points": data_points,
    }
