"""Price anomaly detection — Issue #60.

Statistical anomaly detection for commodity prices:
- Z-score spike/drop alerts (2σ warning, 3σ critical)
- Momentum detection (3 consecutive days rising > 1σ)
- Bollinger-style price bands for the frontend chart

Two flavours:
- Async functions (AsyncSession) called from FastAPI endpoints
- Sync function (psycopg2) called from the Celery beat task
"""

import json
import logging
import math
from datetime import datetime, timezone

import psycopg2
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings

logger = logging.getLogger(__name__)


# ── Async helpers (used by API endpoints) ────────────────────────────


async def get_price_bands(db: AsyncSession, commodity: str) -> dict:
    """Return Bollinger-style price bands for a commodity.

    Returns:
        {mean, std, upper_2σ, lower_2σ, upper_1σ, lower_1σ,
         current_price, percentile, data_points}
    """
    # 30-day stats
    stats_result = await db.execute(
        text("""
            SELECT AVG(price) AS mean,
                   STDDEV_POP(price) AS std,
                   COUNT(*) AS cnt
            FROM commodity_prices
            WHERE commodity = :commodity
              AND time > NOW() - INTERVAL '30 days'
        """),
        {"commodity": commodity},
    )
    stats = stats_result.mappings().first()

    if not stats or stats["cnt"] == 0 or stats["mean"] is None:
        return {
            "commodity": commodity,
            "mean": None,
            "std": None,
            "upper_2s": None,
            "lower_2s": None,
            "upper_1s": None,
            "lower_1s": None,
            "current_price": None,
            "percentile": None,
            "data_points": 0,
        }

    mean = float(stats["mean"])
    std = float(stats["std"]) if stats["std"] else 0.0

    # Latest price
    latest_result = await db.execute(
        text("""
            SELECT price
            FROM commodity_prices
            WHERE commodity = :commodity
            ORDER BY time DESC
            LIMIT 1
        """),
        {"commodity": commodity},
    )
    latest_row = latest_result.mappings().first()
    current_price = float(latest_row["price"]) if latest_row else None

    # Percentile: rank of current price vs last 90 days
    percentile = None
    if current_price is not None:
        pct_result = await db.execute(
            text("""
                SELECT COUNT(*) FILTER (WHERE price <= :current) AS below,
                       COUNT(*) AS total
                FROM commodity_prices
                WHERE commodity = :commodity
                  AND time > NOW() - INTERVAL '90 days'
            """),
            {"commodity": commodity, "current": current_price},
        )
        pct = pct_result.mappings().first()
        if pct and pct["total"] > 0:
            percentile = round(100.0 * pct["below"] / pct["total"], 1)

    # Daily time series with rolling bands (for chart overlay)
    band_result = await db.execute(
        text("""
            WITH daily AS (
                SELECT DATE(time) AS day,
                       AVG(price) AS price
                FROM commodity_prices
                WHERE commodity = :commodity
                  AND time > NOW() - INTERVAL '90 days'
                GROUP BY DATE(time)
                ORDER BY day
            ),
            rolling AS (
                SELECT day,
                       price,
                       AVG(price) OVER w AS rolling_mean,
                       STDDEV_POP(price) OVER w AS rolling_std
                FROM daily
                WINDOW w AS (ORDER BY day ROWS BETWEEN 29 PRECEDING AND CURRENT ROW)
            )
            SELECT day, price, rolling_mean, rolling_std
            FROM rolling
            ORDER BY day
        """),
        {"commodity": commodity},
    )
    band_rows = band_result.mappings().all()
    bands_series = []
    for r in band_rows:
        rm = float(r["rolling_mean"]) if r["rolling_mean"] else None
        rs = float(r["rolling_std"]) if r["rolling_std"] is not None else 0.0
        bands_series.append({
            "date": r["day"].isoformat() if hasattr(r["day"], "isoformat") else str(r["day"]),
            "price": round(float(r["price"]), 4),
            "mean": round(rm, 4) if rm else None,
            "upper_1s": round(rm + rs, 4) if rm else None,
            "lower_1s": round(rm - rs, 4) if rm else None,
            "upper_2s": round(rm + 2 * rs, 4) if rm else None,
            "lower_2s": round(rm - 2 * rs, 4) if rm else None,
        })

    return {
        "commodity": commodity,
        "mean": round(mean, 4),
        "std": round(std, 4),
        "upper_2s": round(mean + 2 * std, 4),
        "lower_2s": round(mean - 2 * std, 4),
        "upper_1s": round(mean + std, 4),
        "lower_1s": round(mean - std, 4),
        "current_price": round(current_price, 4) if current_price else None,
        "percentile": percentile,
        "data_points": int(stats["cnt"]),
        "bands": bands_series,
    }


# ── Sync detection (called from Celery beat task) ───────────────────


def detect_price_anomalies_sync() -> list[dict]:
    """Detect statistical price anomalies across all commodities.

    Called from the Celery beat task. Uses sync psycopg2.

    For each commodity:
    - Compute 30-day rolling mean and std
    - Flag z-score spikes/drops (2σ = warning, 3σ = critical)
    - Detect momentum: 3 consecutive daily prices rising > 1σ

    Dedup: skip if a similar alert exists within the last 6 hours.

    Returns list of created alerts (dicts).
    """
    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    created_alerts: list[dict] = []

    try:
        with conn.cursor() as cur:
            # Get distinct commodities with recent data
            cur.execute("""
                SELECT DISTINCT commodity
                FROM commodity_prices
                WHERE time > NOW() - INTERVAL '30 days'
            """)
            commodities = [row[0] for row in cur.fetchall()]

            for commodity in commodities:
                alerts = _check_commodity(cur, commodity)
                created_alerts.extend(alerts)

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    if created_alerts:
        _publish_alerts_to_redis(created_alerts)

    logger.info(
        "Price anomaly detection complete: %d alerts across %d commodities",
        len(created_alerts),
        len(commodities) if 'commodities' in dir() else 0,
    )
    return created_alerts


def _check_commodity(cur, commodity: str) -> list[dict]:
    """Check a single commodity for z-score anomalies and momentum."""
    alerts = []

    # 30-day stats
    cur.execute("""
        SELECT AVG(price) AS mean, STDDEV_POP(price) AS std, COUNT(*) AS cnt
        FROM commodity_prices
        WHERE commodity = %s AND time > NOW() - INTERVAL '30 days'
    """, (commodity,))
    row = cur.fetchone()
    if not row or row[2] < 5:
        return alerts  # not enough data

    mean, std, cnt = float(row[0]), float(row[1]) if row[1] else 0.0, row[2]
    if std == 0:
        return alerts  # no variance

    # Latest price
    cur.execute("""
        SELECT price FROM commodity_prices
        WHERE commodity = %s ORDER BY time DESC LIMIT 1
    """, (commodity,))
    latest = cur.fetchone()
    if not latest:
        return alerts
    price = float(latest[0])

    z_score = (price - mean) / std

    # ── Z-score spike / drop alerts ──
    if abs(z_score) >= 2.0:
        severity = "critical" if abs(z_score) >= 3.0 else "warning"
        direction = "above" if z_score > 0 else "below"
        alert_type = "price_spike" if z_score > 0 else "price_drop"
        title = f"{_fmt(commodity)} price {'spike' if z_score > 0 else 'drop'} detected"
        body = (
            f"{_fmt(commodity)} price at ${price:.2f} — "
            f"{abs(z_score):.1f}\u03c3 {direction} 30-day average "
            f"(${mean:.2f}\u00b1${std:.2f})"
        )

        if not _alert_exists_recently(cur, commodity, alert_type, hours=6):
            alert = _insert_alert(
                cur, commodity, alert_type, severity, title, body,
                metadata={"z_score": round(z_score, 2), "mean": round(mean, 2),
                          "std": round(std, 2), "price": round(price, 2)},
            )
            alerts.append(alert)

    # ── Momentum detection: 3 consecutive daily prices rising > 1σ ──
    cur.execute("""
        WITH daily AS (
            SELECT DATE(time) AS day, AVG(price) AS avg_price
            FROM commodity_prices
            WHERE commodity = %s AND time > NOW() - INTERVAL '5 days'
            GROUP BY DATE(time)
            ORDER BY day DESC
            LIMIT 4
        )
        SELECT day, avg_price FROM daily ORDER BY day ASC
    """, (commodity,))
    daily_rows = cur.fetchall()

    if len(daily_rows) >= 4:
        # Check last 3 consecutive daily changes
        changes = []
        for i in range(1, len(daily_rows)):
            changes.append(float(daily_rows[i][1]) - float(daily_rows[i - 1][1]))

        last_3 = changes[-3:] if len(changes) >= 3 else changes
        if len(last_3) == 3 and all(c > std for c in last_3):
            if not _alert_exists_recently(cur, commodity, "price_trend", hours=6):
                total_rise = sum(last_3)
                title = f"{_fmt(commodity)} sustained upward momentum"
                body = (
                    f"{_fmt(commodity)} price rising for 3 consecutive days "
                    f"(+${total_rise:.2f} total), each day > 1\u03c3 (${std:.2f})"
                )
                alert = _insert_alert(
                    cur, commodity, "price_trend", "warning", title, body,
                    metadata={"daily_changes": [round(c, 2) for c in last_3],
                              "std": round(std, 2)},
                )
                alerts.append(alert)

    return alerts


def _alert_exists_recently(cur, commodity: str, alert_type: str, hours: int = 6) -> bool:
    """Check if a similar alert was already created within the last N hours."""
    cur.execute("""
        SELECT 1 FROM alert_events
        WHERE commodity = %s AND type = %s
          AND time > NOW() - make_interval(hours => %s)
        LIMIT 1
    """, (commodity, alert_type, hours))
    return cur.fetchone() is not None


def _insert_alert(cur, commodity, alert_type, severity, title, body, metadata=None) -> dict:
    """Insert an alert_events row and return it as a dict."""
    now = datetime.now(timezone.utc)
    meta_json = json.dumps(metadata) if metadata else None

    cur.execute("""
        INSERT INTO alert_events (time, type, severity, title, body, commodity, source, metadata, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)
        RETURNING id, time
    """, (now, alert_type, severity, title, body, commodity, "price_anomaly", meta_json))
    row = cur.fetchone()

    alert = {
        "id": str(row[0]),
        "time": row[1].isoformat() if hasattr(row[1], "isoformat") else str(row[1]),
        "type": alert_type,
        "severity": severity,
        "title": title,
        "body": body,
        "commodity": commodity,
        "source": "price_anomaly",
        "metadata": metadata,
    }
    logger.info("Created %s alert for %s: %s", alert_type, commodity, title)
    return alert


def _publish_alerts_to_redis(alerts: list[dict]):
    """Publish new alerts to Redis pub/sub for SSE clients."""
    try:
        import redis as sync_redis
        r = sync_redis.from_url(settings.REDIS_URL)
        for alert in alerts:
            r.publish("alerts", json.dumps(alert, default=str))
        r.close()
    except Exception as exc:
        logger.warning("Failed to publish alerts to Redis: %s", exc)


def _fmt(commodity: str) -> str:
    """Format commodity name: crude_oil -> Crude Oil."""
    return commodity.replace("_", " ").title()
