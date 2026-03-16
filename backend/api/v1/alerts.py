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

from dependencies import get_db
from middleware.auth import require_auth
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("")
async def list_alerts(
    alert_type: str | None = Query(None, description="Filter: news_event, ais_anomaly, price_spike"),
    severity: str | None = Query(None, description="Filter: info, warning, critical"),
    commodity: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, le=100),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """List recent alerts with optional filters."""
    conditions = []
    params: dict[str, Any] = {"limit": limit, "offset": offset}

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

    # Get total count
    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM alert_events {where}"),
        params,
    )
    total = count_result.scalar()

    result = await db.execute(
        text(f"""
            SELECT id, type, severity, commodity, title, body,
                   source, source_url, metadata, time
            FROM alert_events
            {where}
            ORDER BY time DESC
            LIMIT :limit OFFSET :offset
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
        "meta": {"total": total, "offset": offset, "limit": limit},
    }


def _alert_matches_subscriptions(alert_data: dict, subscriptions: list[dict]) -> bool:
    """Check if an alert matches any of the user's subscriptions.

    Severity ordering: info < warning < critical.
    A subscription with min_severity='warning' matches warning and critical.
    """
    if not subscriptions:
        return False

    severity_order = {"info": 0, "warning": 1, "critical": 2}
    alert_severity = alert_data.get("severity", "info")
    alert_type = alert_data.get("type")
    alert_commodity = alert_data.get("commodity")

    for sub in subscriptions:
        # Check commodity filter
        if sub["commodity"] and sub["commodity"] != alert_commodity:
            continue
        # Check alert_type filter
        if sub["alert_type"] and sub["alert_type"] != alert_type:
            continue
        # Check severity threshold
        min_sev = severity_order.get(sub["min_severity"], 0)
        alert_sev = severity_order.get(alert_severity, 0)
        if alert_sev < min_sev:
            continue
        return True

    return False


async def _load_user_subscriptions(clerk_id: str) -> list[dict]:
    """Load user's alert subscriptions from DB."""
    from main import engine
    from sqlalchemy.ext.asyncio import async_sessionmaker

    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as db:
        result = await db.execute(
            text("""
                SELECT s.commodity, s.alert_type, s.min_severity
                FROM user_alert_subscriptions s
                JOIN users u ON u.id = s.user_id
                WHERE u.clerk_user_id = :clerk_id
            """),
            {"clerk_id": clerk_id},
        )
        return [dict(row) for row in result.mappings().all()]


async def _sse_generator(request: Request, subscriptions: list[dict]) -> AsyncGenerator[str, None]:
    """Generate SSE events from Redis pub/sub + heartbeat.

    Listens to 'alerts' channel on Redis. Filters alerts based on user's
    subscriptions. Sends heartbeat every 30s. Auto-disconnects after 1 hour.
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

                # Filter: only send alerts matching user's subscriptions
                try:
                    alert_obj = json.loads(data)
                except (json.JSONDecodeError, TypeError):
                    alert_obj = {}

                if _alert_matches_subscriptions(alert_obj, subscriptions):
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

    Sends new alerts as they arrive via Redis pub/sub, filtered by user's
    alert subscriptions. Heartbeat every 30s. Auto-closes after 1 hour.
    """
    clerk_id = user.get("sub")
    subscriptions = await _load_user_subscriptions(clerk_id)

    return StreamingResponse(
        _sse_generator(request, subscriptions),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
