"""Alert endpoints — /api/v1/alerts/*

- GET  /alerts         — list alerts (filterable)
- GET  /alerts/stream  — SSE live alert feed
- GET  /alerts/stats   — alert count by type/severity
"""

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db, get_redis
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("")
async def list_alerts(
    type: str | None = Query(None, description="Filter: news_event, ais_anomaly, price_move, etc."),
    severity: str | None = Query(None, description="Filter: info, warning, critical"),
    priority: str | None = Query(None, description="Filter: critical, high, medium, low"),
    commodity: str | None = Query(None, description="Filter by commodity"),
    unread: bool | None = Query(None, description="Filter unread only"),
    active_only: bool = Query(True, description="Only active (unresolved) alerts"),
    hours: int = Query(24, le=168, description="Lookback hours (max 7 days)"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """List alert events with optional filters."""
    conditions = ["time > NOW() - make_interval(hours => :hours)"]
    params: dict[str, Any] = {"hours": hours, "limit": limit, "offset": offset}

    if type:
        conditions.append("type = :type")
        params["type"] = type
    if severity:
        conditions.append("severity = :severity")
        params["severity"] = severity
    if commodity:
        conditions.append("commodity = :commodity")
        params["commodity"] = commodity
    if priority:
        conditions.append("severity = :priority")
        params["priority"] = priority
    if unread is True:
        conditions.append("(is_read = FALSE OR is_read IS NULL)")
    if active_only:
        conditions.append("is_active = TRUE")
        conditions.append("(snoozed_until IS NULL OR snoozed_until < NOW())")

    where = " AND ".join(conditions)

    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM alert_events WHERE {where}"), params
    )
    total = count_result.scalar()

    result = await db.execute(
        text(f"""
            SELECT id, time, type, severity, title, body, commodity, region,
                   port_id, mmsi, source, source_url, metadata, is_active, resolved_at
            FROM alert_events
            WHERE {where}
            ORDER BY time DESC
            LIMIT :limit OFFSET :offset
        """),
        params,
    )
    rows = result.mappings().all()

    return {
        "data": [
            {
                "id": str(r["id"]),
                "time": r["time"].isoformat(),
                "type": r["type"],
                "severity": r["severity"],
                "title": r["title"],
                "body": r["body"],
                "commodity": r["commodity"],
                "region": r["region"],
                "port_id": str(r["port_id"]) if r["port_id"] else None,
                "mmsi": r["mmsi"],
                "source": r["source"],
                "source_url": r["source_url"],
                "metadata": r["metadata"],
                "is_active": r["is_active"],
                "resolved_at": r["resolved_at"].isoformat() if r["resolved_at"] else None,
            }
            for r in rows
        ],
        "meta": {"total": total, "offset": offset, "limit": limit},
    }


@router.patch("/{alert_id}/read")
async def mark_alert_read(
    alert_id: str,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Mark a single alert as read."""
    result = await db.execute(
        text("""
            UPDATE alert_events SET is_read = TRUE, read_at = NOW()
            WHERE id = :alert_id
            RETURNING id
        """),
        {"alert_id": alert_id},
    )
    row = result.fetchone()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Alert not found")
    await db.commit()
    return {"status": "ok", "id": alert_id}


@router.patch("/{alert_id}/snooze")
async def snooze_alert(
    alert_id: str,
    hours: int = Query(4, ge=1, le=168, description="Snooze duration in hours"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Snooze an alert for a given number of hours."""
    result = await db.execute(
        text("""
            UPDATE alert_events
            SET snoozed_until = NOW() + make_interval(hours => :hours)
            WHERE id = :alert_id
            RETURNING id
        """),
        {"alert_id": alert_id, "hours": hours},
    )
    row = result.fetchone()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Alert not found")
    await db.commit()
    return {"status": "ok", "id": alert_id, "snoozed_hours": hours}


@router.patch("/bulk/read")
async def bulk_mark_read(
    alert_ids: list[str] | None = Query(None, description="Alert IDs to mark read (all if omitted)"),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Bulk mark alerts as read."""
    if alert_ids:
        result = await db.execute(
            text("""
                UPDATE alert_events SET is_read = TRUE, read_at = NOW()
                WHERE id = ANY(:ids) AND is_read = FALSE
            """),
            {"ids": alert_ids},
        )
    else:
        result = await db.execute(
            text("""
                UPDATE alert_events SET is_read = TRUE, read_at = NOW()
                WHERE is_read = FALSE AND is_active = TRUE
            """)
        )
    await db.commit()
    return {"status": "ok", "updated": result.rowcount}


@router.get("/stats")
async def alert_stats(
    hours: int = Query(24, le=168),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Get alert counts grouped by type and severity."""
    result = await db.execute(
        text("""
            SELECT type, severity, COUNT(*) as count
            FROM alert_events
            WHERE time > NOW() - make_interval(hours => :hours)
              AND is_active = TRUE
            GROUP BY type, severity
            ORDER BY count DESC
        """),
        {"hours": hours},
    )
    rows = result.mappings().all()

    return {
        "data": [
            {"type": r["type"], "severity": r["severity"], "count": r["count"]}
            for r in rows
        ],
        "period_hours": hours,
    }


@router.get("/stream")
async def stream_alerts(
    user: dict[str, Any] = Depends(check_api_rate_limit),
):
    """SSE live feed of new alerts via Redis pub/sub.

    Sends heartbeat every 30s. Auto-disconnects after 1 hour.
    """
    redis = await get_redis()

    async def event_generator():
        pubsub = redis.pubsub()
        await pubsub.subscribe("alerts")
        try:
            yield f"data: {json.dumps({'status': 'connected'})}\n\n"
            timeout_count = 0
            max_timeouts = 120  # 120 * 30s = 1 hour

            while timeout_count < max_timeouts:
                try:
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True),
                        timeout=30.0,
                    )
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    timeout_count += 1
                    continue

                if message and message["type"] == "message":
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    yield f"data: {data}\n\n"
        finally:
            await pubsub.unsubscribe("alerts")
            await pubsub.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
