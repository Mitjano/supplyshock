"""Slack notification channel — sends alerts via Incoming Webhooks."""

import logging

import httpx

logger = logging.getLogger(__name__)


async def send_slack(webhook_url: str, alert: dict) -> bool:
    """POST a rich Block Kit message to a Slack incoming webhook.

    Returns True on success, False on failure.
    """
    severity_emoji = {
        "critical": ":rotating_light:",
        "high": ":warning:",
        "medium": ":large_blue_circle:",
        "low": ":white_circle:",
    }
    severity = alert.get("severity", "medium")
    emoji = severity_emoji.get(severity, ":bell:")

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} SupplyShock Alert",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Type:*\n{alert.get('type', 'unknown')}"},
                {"type": "mrkdwn", "text": f"*Severity:*\n{severity}"},
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": alert.get("message", "No details available."),
            },
        },
    ]

    if alert.get("commodity"):
        blocks[1]["fields"].append(
            {"type": "mrkdwn", "text": f"*Commodity:*\n{alert['commodity']}"}
        )

    payload = {"blocks": blocks, "text": alert.get("message", "SupplyShock Alert")}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()
            return True
    except httpx.HTTPError as exc:
        logger.error("Slack notification failed: %s", exc)
        return False
