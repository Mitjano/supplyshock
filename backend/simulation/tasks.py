import asyncio

from celery import Celery
from celery.schedules import crontab
from config import settings

celery_app = Celery(
    "supplyshock",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_time_limit=600,
    beat_schedule={
        "refresh-vessel-positions": {
            "task": "refresh_latest_vessel_positions",
            "schedule": 30.0,
        },
        "ingest-eia-prices": {
            "task": "ingest_eia_prices",
            "schedule": crontab(minute=0, hour="*/6"),  # every 6 hours
        },
        "ingest-nasdaq-prices": {
            "task": "ingest_nasdaq_prices",
            "schedule": crontab(minute=15, hour="*"),  # every hour at :15
        },
        "ingest-gdelt-alerts": {
            "task": "ingest_gdelt_alerts",
            "schedule": crontab(minute="*/15"),  # every 15 minutes
        },
        "detect-ais-anomalies": {
            "task": "detect_ais_anomalies",
            "schedule": crontab(minute="*/30"),  # every 30 minutes
        },
    },
)


# ── Materialized view refresh ──

@celery_app.task(name="refresh_latest_vessel_positions")
def refresh_latest_vessel_positions():
    """Refresh the latest_vessel_positions materialized view (every 30s)."""
    import psycopg2
    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY latest_vessel_positions")
    finally:
        conn.close()


# ── Price ingestion ──

@celery_app.task(name="ingest_eia_prices")
def ingest_eia_prices_task():
    """Fetch EIA energy prices (crude oil, LNG, coal)."""
    from ingestion.eia import ingest_eia_prices
    return ingest_eia_prices()


@celery_app.task(name="ingest_nasdaq_prices")
def ingest_nasdaq_prices_task():
    """Fetch Nasdaq Data Link prices (metals, agriculture)."""
    from ingestion.prices import ingest_nasdaq_prices
    return ingest_nasdaq_prices()


# ── Alert ingestion ──

@celery_app.task(name="ingest_gdelt_alerts")
def ingest_gdelt_alerts_task():
    """Poll GDELT for supply chain news events."""
    from ingestion.gdelt import ingest_gdelt_alerts
    return ingest_gdelt_alerts()


# ── AIS anomaly detection (Issue #19) ──

@celery_app.task(name="detect_ais_anomalies")
def detect_ais_anomalies():
    """Check vessel congestion at bottleneck nodes.

    For each bottleneck_node, count vessels within 50km radius.
    If count > mean + 2*std (30-day rolling), generate AIS_ANOMALY alert.
    """
    import json
    import psycopg2
    import redis as sync_redis
    from datetime import datetime, timezone

    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        with conn.cursor() as cur:
            # Get bottleneck nodes with coordinates
            cur.execute("""
                SELECT id, slug, name, latitude, longitude, baseline_risk
                FROM bottleneck_nodes
                WHERE latitude IS NOT NULL AND longitude IS NOT NULL
            """)
            nodes = cur.fetchall()

            for node_id, slug, name, lat, lon, baseline_risk in nodes:
                # Count vessels within ~50km (0.45 degrees approx)
                cur.execute("""
                    SELECT COUNT(DISTINCT mmsi) as cnt,
                           AVG(speed_knots) as avg_speed
                    FROM vessel_positions
                    WHERE time > NOW() - INTERVAL '1 hour'
                      AND latitude BETWEEN %s AND %s
                      AND longitude BETWEEN %s AND %s
                """, (lat - 0.45, lat + 0.45, lon - 0.45, lon + 0.45))

                result = cur.fetchone()
                vessel_count = result[0] or 0
                avg_speed = result[1]

                # Calculate congestion index (0-100)
                congestion = min(vessel_count * 2, 100)
                risk_level = "critical" if congestion > 80 else "warning" if congestion > 50 else "normal"

                # Insert status record
                cur.execute("""
                    INSERT INTO chokepoint_status (node_id, vessel_count, avg_speed_knots,
                        congestion_index, risk_level, time)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                """, (node_id, vessel_count, avg_speed, congestion, risk_level))

                # Check for anomaly: get 30-day stats
                cur.execute("""
                    SELECT AVG(vessel_count), STDDEV(vessel_count)
                    FROM chokepoint_status
                    WHERE node_id = %s AND time > NOW() - INTERVAL '30 days'
                """, (node_id,))
                stats = cur.fetchone()
                mean_count = stats[0] or 0
                std_count = stats[1] or 0

                # Anomaly if > mean + 2*std and at least 10 vessels
                threshold = mean_count + 2 * std_count
                if vessel_count > threshold and vessel_count >= 10 and std_count > 0:
                    cur.execute("""
                        INSERT INTO alert_events (type, severity, title, body,
                            source, metadata, time)
                        VALUES ('ais_anomaly', 'warning',
                            %s, %s, %s, %s, NOW())
                    """, (
                        f"Unusual vessel congestion at {name}",
                        f"{vessel_count} vessels detected (normal: {mean_count:.0f}±{std_count:.0f})",
                        "ais_anomaly",
                        json.dumps({"node_slug": slug, "vessel_count": vessel_count,
                                    "threshold": threshold, "congestion_index": congestion}),
                    ))

                    # Publish alert via Redis
                    try:
                        r = sync_redis.from_url(settings.REDIS_URL)
                        r.publish("alerts", json.dumps({
                            "type": "ais_anomaly",
                            "severity": "warning",
                            "title": f"Unusual vessel congestion at {name}",
                            "node_slug": slug,
                            "vessel_count": vessel_count,
                            "time": datetime.now(timezone.utc).isoformat(),
                        }))
                        r.close()
                    except Exception:
                        pass

        conn.commit()
    finally:
        conn.close()


# ── AIS WebSocket consumer ──

@celery_app.task(name="start_ais_stream", bind=True, max_retries=3)
def start_ais_stream(self):
    """Start the AIS WebSocket consumer as a long-running Celery task."""
    from ingestion.ais_stream import run_ais_consumer

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_ais_consumer())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)
    finally:
        loop.close()
