"""Alert endpoints — /api/v1/alerts/*

- GET /alerts          — list recent alerts
- GET /alerts/stream   — SSE live feed
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from middleware.auth import require_auth

router = APIRouter(prefix="/alerts", tags=["Alerts"])


async def _get_db():
    from main import engine
    from sqlalchemy.ext.asyncio import async_sessionmaker

    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


@router.get("")
async def list_alerts(
    alert_type: str | None = Query(None, description="Filter: news_event, ais_anomaly, price_spike"),
    severity: str | None = Query(None, description="Filter: info, warning, critical"),
    commodity: str | None = Query(None),
    limit: int = Query(20, le=100),
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(_get_db),
):
    """List recent alerts with optional filters."""
    conditions = []
    params: dict[str, Any] = {"limit": limit}

    if alert_type:
        conditions.append("type = :alert_type")
        params["alert_type"] = alert_type

    if severity:
        conditions.append("severity = :severity")
        params["severity"] = severity

    if commodity:
        conditions.append("commodity = :commodity")
        params["commodity"] = commodity

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    result = await db.execute(
        text(f"""
            SELECT id, type, severity, commodity, title, body,
                   source, source_url, metadata, time
            FROM alert_events
            {where}
            ORDER BY time DESC
            LIMIT :limit
        """),
        params,
    )
    rows = result.mappings().all()

    return {
        "data": [
            {
                "id": str(row["id"]),
                "type": row["type"],
                "severity": row["severity"],
                "commodity": row["commodity"],
                "title": row["title"],
                "body": row["body"],
                "source": row["source"],
                "source_url": row["source_url"],
                "metadata": row["metadata"],
                "time": row["time"].isoformat(),
            }
            for row in rows
        ],
        "meta": {"total": len(rows), "limit": limit},
    }


async def _sse_generator(request: Request) -> AsyncGenerator[str, None]:
    """Generate SSE events from Redis pub/sub + heartbeat.

    Listens to 'alerts' channel on Redis. Sends heartbeat every 30s.
    Auto-disconnects after 1 hour.
    """
    from main import redis_client

    pubsub = redis_client.pubsub()
    await pubsub.subscribe("alerts")

    start_time = asyncio.get_event_loop().time()
    max_duration = 3600  # 1 hour

    try:
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break

            # Check max duration
            if asyncio.get_event_loop().time() - start_time > max_duration:
                yield f"event: close\ndata: {{\"reason\": \"max_duration\"}}\n\n"
                break

            # Check for new messages (non-blocking, 1s timeout)
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                yield f"event: alert\ndata: {data}\n\n"
            else:
                # Send heartbeat every ~30 iterations (30s with 1s timeout)
                elapsed = asyncio.get_event_loop().time() - start_time
                if int(elapsed) % 30 == 0 and int(elapsed) > 0:
                    yield f"event: heartbeat\ndata: {{\"time\": \"{datetime.now(timezone.utc).isoformat()}\"}}\n\n"

            await asyncio.sleep(1)
    finally:
        await pubsub.unsubscribe("alerts")
        await pubsub.close()


@router.get("/stream")
async def alerts_stream(
    request: Request,
    user: dict[str, Any] = Depends(require_auth),
):
    """SSE endpoint for live alert feed.

    Sends new alerts as they arrive via Redis pub/sub.
    Heartbeat every 30s. Auto-closes after 1 hour.
    """
    return StreamingResponse(
        _sse_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
