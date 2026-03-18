"""Central alert dispatcher — fans out alerts to user notification channels.

Rate-limited to 10 messages per hour per channel via Redis counters.
"""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from notifications.slack import send_slack
from notifications.telegram import send_telegram
from notifications.discord import send_discord

logger = logging.getLogger(__name__)

MAX_PER_HOUR = 10
RATE_LIMIT_TTL = 3600  # seconds


async def _check_rate_limit(redis, channel_id: str) -> bool:
    """Return True if the channel is under the rate limit."""
    key = f"notif:rate:{channel_id}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, RATE_LIMIT_TTL)
    return count <= MAX_PER_HOUR


async def dispatch_alert(db: AsyncSession, alert_data: dict) -> dict:
    """Dispatch an alert to all matching user notification channels.

    1. Query alert_subscriptions for users subscribed to this alert type.
    2. For each user, query their notification_channels.
    3. Send to each enabled channel (respecting rate limits).

    Returns a summary dict with counts.
    """
    from dependencies import get_redis

    redis = await get_redis()
    alert_type = alert_data.get("type", "")

    # Find users subscribed to this alert type
    subs_result = await db.execute(
        text("""
            SELECT DISTINCT user_id
            FROM alert_subscriptions
            WHERE :alert_type = ANY(string_to_array(events, ','))
               OR events = '*'
        """),
        {"alert_type": alert_type},
    )
    user_ids = [row[0] for row in subs_result.fetchall()]

    sent = 0
    rate_limited = 0
    failed = 0

    for user_id in user_ids:
        channels_result = await db.execute(
            text("""
                SELECT id, channel_type, webhook_url, bot_token, chat_id, events
                FROM notification_channels
                WHERE user_id = :uid AND enabled = true
            """),
            {"uid": str(user_id)},
        )
        channels = channels_result.mappings().all()

        for ch in channels:
            # Check if channel subscribes to this event
            ch_events = (ch["events"] or "").split(",")
            if "*" not in ch_events and alert_type not in ch_events:
                continue

            # Rate-limit check
            if not await _check_rate_limit(redis, str(ch["id"])):
                rate_limited += 1
                logger.warning("Rate limit hit for channel %s", ch["id"])
                continue

            ok = False
            try:
                if ch["channel_type"] == "slack":
                    ok = await send_slack(ch["webhook_url"], alert_data)
                elif ch["channel_type"] == "telegram":
                    ok = await send_telegram(ch["bot_token"], ch["chat_id"], alert_data)
                elif ch["channel_type"] == "discord":
                    ok = await send_discord(ch["webhook_url"], alert_data)
                else:
                    logger.warning("Unknown channel type: %s", ch["channel_type"])
            except Exception:
                logger.exception("Error sending to channel %s", ch["id"])

            if ok:
                sent += 1
            else:
                failed += 1

    return {"sent": sent, "rate_limited": rate_limited, "failed": failed, "users": len(user_ids)}
