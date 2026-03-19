"""Webhook delivery engine.

Queries user_webhooks for matching event subscriptions and POSTs
JSON payloads with HMAC-SHA256 signatures. Retries once on failure.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

DELIVERY_TIMEOUT = 10  # seconds per POST


async def deliver_webhook(
    db: AsyncSession,
    event_type: str,
    payload: dict,
) -> list[dict]:
    """Deliver a webhook event to all matching subscribers.

    Args:
        db: Async database session.
        event_type: One of alert.created, voyage.started, voyage.arrived, price.anomaly.
        payload: JSON-serialisable event payload.

    Returns:
        List of delivery result dicts with url, status, and attempt info.
    """
    # Find all webhooks subscribed to this event_type.
    # Events are stored as comma-separated strings in the DB.
    result = await db.execute(
        text("""
            SELECT id, user_id, url, secret, events
            FROM user_webhooks
            WHERE events LIKE :pattern
        """),
        {"pattern": f"%{event_type}%"},
    )
    webhooks = result.mappings().all()

    if not webhooks:
        logger.info("No webhooks subscribed to event_type=%s", event_type)
        return []

    body = json.dumps({
        "event": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": payload,
    }, default=str)

    results = []

    async with httpx.AsyncClient(timeout=DELIVERY_TIMEOUT) as client:
        for wh in webhooks:
            # Verify the event is actually in the subscription list
            subscribed_events = [e.strip() for e in wh["events"].split(",")]
            if event_type not in subscribed_events:
                continue

            delivery_id = str(uuid.uuid4())
            signature = hmac.new(
                wh["secret"].encode(),
                body.encode(),
                hashlib.sha256,
            ).hexdigest()

            headers = {
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature,
                "X-Webhook-Event": event_type,
                "X-Webhook-Delivery-ID": delivery_id,
            }

            delivery = {
                "webhook_id": str(wh["id"]),
                "url": wh["url"],
                "event": event_type,
            }

            # Attempt delivery (+ 1 retry)
            for attempt in range(1, 3):
                try:
                    resp = await client.post(wh["url"], content=body, headers=headers)
                    delivery["status"] = resp.status_code
                    delivery["attempt"] = attempt
                    delivery["success"] = 200 <= resp.status_code < 300

                    if delivery["success"]:
                        logger.info(
                            "Webhook delivered: id=%s url=%s event=%s attempt=%d status=%d",
                            wh["id"], wh["url"], event_type, attempt, resp.status_code,
                        )
                        break
                    else:
                        logger.warning(
                            "Webhook non-2xx: id=%s url=%s status=%d attempt=%d",
                            wh["id"], wh["url"], resp.status_code, attempt,
                        )
                        if attempt == 2:
                            break
                        await asyncio.sleep(10 * attempt)

                except Exception as exc:
                    delivery["status"] = None
                    delivery["attempt"] = attempt
                    delivery["success"] = False
                    delivery["error"] = str(exc)
                    logger.error(
                        "Webhook delivery failed: id=%s url=%s attempt=%d error=%s",
                        wh["id"], wh["url"], attempt, exc,
                    )
                    if attempt == 2:
                        break
                    await asyncio.sleep(10 * attempt)

            results.append(delivery)

    logger.info(
        "Webhook delivery complete: event=%s total=%d succeeded=%d",
        event_type,
        len(results),
        sum(1 for r in results if r.get("success")),
    )

    return results
