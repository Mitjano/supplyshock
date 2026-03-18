"""Chat endpoint — /api/v1/chat

POST /chat — accepts {"message": str}, returns SSE stream of AI response tokens.
Rate limited per plan: Free=10/day, Pro=100/day, Business/Enterprise=unlimited.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ai.chat_engine import ChatEngine
from auth.rbac import _get_user_plan
from dependencies import get_db, get_redis
from middleware.auth import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])

# Daily chat message limits per plan
CHAT_LIMITS: dict[str, int | None] = {
    "free": 10,
    "pro": 100,
    "business": None,   # unlimited
    "enterprise": None,  # unlimited
}

# TTL for rate limit keys (48 hours as specified)
CHAT_KEY_TTL = 48 * 3600

# Singleton engine (reuses the Anthropic client)
_engine = ChatEngine()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


async def _check_chat_rate_limit(
    user: dict[str, Any],
    redis,
) -> tuple[int, int | None]:
    """Check and increment daily chat usage. Returns (current_count, limit).

    Raises 429 if limit exceeded.
    """
    user_plan = _get_user_plan(user)
    limit = CHAT_LIMITS.get(user_plan)

    # Unlimited plans skip the check
    if limit is None:
        return 0, None

    clerk_user_id = user.get("sub", "unknown")
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    key = f"chat:{clerk_user_id}:daily:{today}"

    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, CHAT_KEY_TTL)

    if current > limit:
        raise HTTPException(
            status_code=429,
            detail={
                "error": f"Daily chat limit reached ({limit} messages per day on {user_plan} plan)",
                "code": "CHAT_RATE_LIMIT",
                "limit": limit,
                "used": current,
                "current_plan": user_plan,
            },
            headers={"Retry-After": "3600"},
        )

    return current, limit


@router.post("")
async def chat(
    body: ChatRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """Stream AI chat response as Server-Sent Events."""
    used, limit = await _check_chat_rate_limit(user, redis)
    user_plan = _get_user_plan(user)

    async def event_generator():
        try:
            # Send metadata first
            meta = {"type": "meta", "used": used, "limit": limit}
            yield f"data: {json.dumps(meta)}\n\n"

            # Stream AI response tokens
            async for chunk in _engine.chat(body.message, user_plan, db):
                payload = {"type": "token", "content": chunk}
                yield f"data: {json.dumps(payload)}\n\n"

            # Signal completion
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            logger.exception("Chat stream error")
            error_payload = {"type": "error", "message": "An error occurred while generating the response."}
            yield f"data: {json.dumps(error_payload)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
