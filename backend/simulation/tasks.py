import asyncio

from celery import Celery
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
            "schedule": 30.0,  # every 30 seconds
        },
    },
)


@celery_app.task(name="refresh_latest_vessel_positions")
def refresh_latest_vessel_positions():
    """Refresh the latest_vessel_positions materialized view.

    Runs every 30s via Celery Beat. Uses CONCURRENTLY so reads aren't blocked.
    """
    import psycopg2
    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY latest_vessel_positions")
    finally:
        conn.close()


@celery_app.task(name="start_ais_stream", bind=True, max_retries=3)
def start_ais_stream(self):
    """Start the AIS WebSocket consumer as a long-running Celery task.

    This task runs indefinitely (auto-reconnect inside).
    Set task_time_limit high or use a dedicated worker.
    """
    from ingestion.ais_stream import run_ais_consumer

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_ais_consumer())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)
    finally:
        loop.close()
