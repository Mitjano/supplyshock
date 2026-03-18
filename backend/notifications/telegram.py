"""Telegram notification channel — sends alerts via Bot API."""

import logging

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


async def send_telegram(bot_token: str, chat_id: str, alert: dict) -> bool:
    """POST a formatted message to the Telegram Bot API.

    Returns True on success, False on failure.
    """
    severity = alert.get("severity", "medium")
    severity_label = {"critical": "🔴 CRITICAL", "high": "🟠 HIGH", "medium": "🔵 MEDIUM", "low": "⚪ LOW"}

    lines = [
        f"<b>SupplyShock Alert</b>",
        f"<b>Type:</b> {alert.get('type', 'unknown')}",
        f"<b>Severity:</b> {severity_label.get(severity, severity)}",
        "",
        alert.get("message", "No details available."),
    ]

    if alert.get("commodity"):
        lines.insert(3, f"<b>Commodity:</b> {alert['commodity']}")

    text = "\n".join(lines)
    url = f"{TELEGRAM_API}/bot{bot_token}/sendMessage"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url,
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            )
            resp.raise_for_status()
            return True
    except httpx.HTTPError as exc:
        logger.error("Telegram notification failed: %s", exc)
        return False
