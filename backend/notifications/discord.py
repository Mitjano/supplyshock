"""Discord notification channel — sends alerts via webhooks."""

import logging

import httpx

logger = logging.getLogger(__name__)

SEVERITY_COLORS = {
    "critical": 0xED4245,  # red
    "high": 0xFFA500,      # orange
    "medium": 0x3498DB,    # blue
    "low": 0x95A5A6,       # grey
}


async def send_discord(webhook_url: str, alert: dict) -> bool:
    """POST a rich embed to a Discord webhook.

    Returns True on success, False on failure.
    """
    severity = alert.get("severity", "medium")
    color = SEVERITY_COLORS.get(severity, 0x3498DB)

    fields = [
        {"name": "Type", "value": alert.get("type", "unknown"), "inline": True},
        {"name": "Severity", "value": severity.upper(), "inline": True},
    ]

    if alert.get("commodity"):
        fields.append({"name": "Commodity", "value": alert["commodity"], "inline": True})

    embed = {
        "title": "SupplyShock Alert",
        "description": alert.get("message", "No details available."),
        "color": color,
        "fields": fields,
        "footer": {"text": "SupplyShock Notifications"},
    }

    payload = {"embeds": [embed]}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()
            return True
    except httpx.HTTPError as exc:
        logger.error("Discord notification failed: %s", exc)
        return False
