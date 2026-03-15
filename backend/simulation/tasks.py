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
)


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
