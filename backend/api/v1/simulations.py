"""Simulation endpoints — /api/v1/simulations/*

CRUD for supply-chain disruption simulations.
- POST   /simulations           — create & queue a simulation
- GET    /simulations           — list user's simulations
- GET    /simulations/{id}      — simulation detail + result
- GET    /simulations/{id}/stream — SSE progress stream
- DELETE /simulations/{id}      — cancel/delete simulation
"""

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db, get_redis, resolve_user_id
from middleware.rate_limit import check_api_rate_limit

router = APIRouter(prefix="/simulations", tags=["Simulations"])


class SimulationCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    node: str = Field(..., min_length=1, max_length=100, description="Bottleneck node slug")
    event_type: str = Field(..., description="e.g. flood, strike, blockade, storm, earthquake")
    description: str | None = Field(None, max_length=2000)
    agents_count: int | None = Field(None, ge=10, le=1000)
    parameters: dict[str, Any] = Field(
        default_factory=lambda: {
            "duration_weeks": 4,
            "intensity": 0.7,
            "agents": 50,
            "horizon_days": 90,
        }
    )


@router.post("")
async def create_simulation(
    body: SimulationCreate,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Create a new simulation and queue it for processing."""
    import json

    user_id = await resolve_user_id(user, db)
    plan = user.get("_db_plan", "free")

    # Check plan limits: free = 3 simulations total
    if plan == "free":
        count_result = await db.execute(
            text("SELECT COUNT(*) FROM simulations WHERE user_id = :uid"),
            {"uid": user_id},
        )
        count = count_result.scalar()
        if count >= 3:
            raise HTTPException(
                status_code=402,
                detail={"error": "Free plan limited to 3 simulations", "code": "PLAN_LIMIT"},
            )

    agents_count = body.agents_count or body.parameters.get("agents", 50)

    result = await db.execute(
        text("""
            INSERT INTO simulations (user_id, title, node, event_type, description, parameters, agents_count, status)
            VALUES (:uid, :title, :node, :event_type, :description, :parameters, :agents_count, 'queued')
            RETURNING id, status, created_at
        """),
        {
            "uid": user_id,
            "title": body.title,
            "node": body.node,
            "event_type": body.event_type,
            "description": body.description,
            "parameters": json.dumps(body.parameters),
            "agents_count": agents_count,
        },
    )
    await db.commit()
    row = result.mappings().first()

    # Queue Celery task
    try:
        from simulation.tasks import celery_app

        task = celery_app.send_task(
            "run_simulation",
            args=[str(row["id"])],
            queue="analytics",
        )
        await db.execute(
            text("UPDATE simulations SET celery_task_id = :tid WHERE id = :sid"),
            {"tid": task.id, "sid": str(row["id"])},
        )
        await db.commit()
    except Exception:
        pass  # Celery not running in dev — simulation stays queued

    return {
        "id": str(row["id"]),
        "status": row["status"],
        "created_at": row["created_at"].isoformat(),
    }


@router.get("")
async def list_simulations(
    status: str | None = Query(None, description="Filter: queued, running, completed, failed"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, le=100),
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """List user's simulations (newest first)."""
    user_id = await resolve_user_id(user, db)
    conditions = ["user_id = :uid"]
    params: dict[str, Any] = {"uid": user_id, "limit": limit, "offset": offset}

    if status:
        conditions.append("status = :status")
        params["status"] = status

    where = " AND ".join(conditions)

    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM simulations WHERE {where}"), params
    )
    total = count_result.scalar()

    result = await db.execute(
        text(f"""
            SELECT id, title, node, event_type, status, progress,
                   agents_count, started_at, completed_at, created_at
            FROM simulations
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        params,
    )
    rows = result.mappings().all()

    return {
        "data": [
            {
                "id": str(r["id"]),
                "title": r["title"],
                "node": r["node"],
                "event_type": r["event_type"],
                "status": r["status"],
                "progress": r["progress"],
                "agents_count": r["agents_count"],
                "started_at": r["started_at"].isoformat() if r["started_at"] else None,
                "completed_at": r["completed_at"].isoformat() if r["completed_at"] else None,
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ],
        "meta": {"total": total, "offset": offset, "limit": limit},
    }


@router.get("/{simulation_id}")
async def get_simulation(
    simulation_id: str,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Get full simulation detail including result."""
    user_id = await resolve_user_id(user, db)

    result = await db.execute(
        text("""
            SELECT id, title, node, event_type, description, parameters,
                   status, progress, progress_log, result, error_message,
                   agents_count, celery_task_id, started_at, completed_at, created_at
            FROM simulations
            WHERE id = :sid AND user_id = :uid
        """),
        {"sid": simulation_id, "uid": user_id},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Simulation not found")

    return {
        "id": str(row["id"]),
        "title": row["title"],
        "node": row["node"],
        "event_type": row["event_type"],
        "description": row["description"],
        "parameters": row["parameters"],
        "status": row["status"],
        "progress": row["progress"],
        "progress_log": row["progress_log"] or [],
        "result": row["result"],
        "error_message": "Simulation failed — check logs for details" if row["error_message"] else None,
        "agents_count": row["agents_count"],
        "started_at": row["started_at"].isoformat() if row["started_at"] else None,
        "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
        "created_at": row["created_at"].isoformat(),
    }


@router.delete("/{simulation_id}")
async def delete_simulation(
    simulation_id: str,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Delete a simulation. If running, revoke the Celery task."""
    user_id = await resolve_user_id(user, db)

    result = await db.execute(
        text("""
            SELECT id, status, celery_task_id FROM simulations
            WHERE id = :sid AND user_id = :uid
        """),
        {"sid": simulation_id, "uid": user_id},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Simulation not found")

    # Revoke Celery task if still running
    if row["status"] in ("queued", "running") and row["celery_task_id"]:
        try:
            from simulation.tasks import celery_app
            celery_app.control.revoke(row["celery_task_id"], terminate=True)
        except Exception:
            pass

    await db.execute(
        text("DELETE FROM simulations WHERE id = :sid"),
        {"sid": simulation_id},
    )
    await db.commit()

    return {"status": "deleted"}


@router.get("/{simulation_id}/stream")
async def stream_simulation_progress(
    simulation_id: str,
    user: dict[str, Any] = Depends(check_api_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """SSE stream of simulation progress updates.

    Emits events:
      data: {"progress": 45, "log": "Processing agents..."}
      data: {"status": "completed", "progress": 100}
      data: {"status": "failed", "error": "..."}

    Stream closes when simulation reaches a terminal state.
    """
    user_id = await resolve_user_id(user, db)

    # Verify ownership
    result = await db.execute(
        text("SELECT id, status FROM simulations WHERE id = :sid AND user_id = :uid"),
        {"sid": simulation_id, "uid": user_id},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Simulation not found")

    # If already in terminal state, return single event
    if row["status"] in ("completed", "failed"):
        async def terminal_stream():
            yield f"data: {json.dumps({'status': row['status'], 'progress': 100})}\n\n"
        return StreamingResponse(terminal_stream(), media_type="text/event-stream")

    redis = await get_redis()

    async def event_generator():
        """Subscribe to Redis pub/sub channel for this simulation."""
        import redis.asyncio as aioredis

        pubsub = redis.pubsub()
        channel = f"sim:{simulation_id}"
        await pubsub.subscribe(channel)

        try:
            # Send initial keepalive
            yield f"data: {json.dumps({'status': 'connected', 'simulation_id': simulation_id})}\n\n"

            timeout_count = 0
            max_timeouts = 120  # 120 * 5s = 10 min max

            while timeout_count < max_timeouts:
                try:
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True),
                        timeout=5.0,
                    )
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield ": keepalive\n\n"
                    timeout_count += 1
                    continue

                if message and message["type"] == "message":
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    yield f"data: {data}\n\n"

                    # Check for terminal state
                    try:
                        parsed = json.loads(data)
                        if parsed.get("status") in ("completed", "failed"):
                            break
                    except (json.JSONDecodeError, TypeError):
                        pass

        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx: disable buffering
        },
    )
