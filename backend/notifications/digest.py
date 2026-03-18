"""Daily digest — groups alerts by category and sends summary email.

Called by Celery beat scheduler once per day.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from emails.resend import send_email

logger = logging.getLogger(__name__)


async def send_daily_digest(db: AsyncSession):
    """Group alerts from the last 24h by category and send summary emails to subscribed users."""
    cutoff = datetime.utcnow() - timedelta(hours=24)

    # Get alert summary grouped by type and severity
    result = await db.execute(
        text("""
            SELECT type, severity, COUNT(*) AS count,
                   ARRAY_AGG(DISTINCT commodity) FILTER (WHERE commodity IS NOT NULL) AS commodities
            FROM alert_events
            WHERE time > :cutoff AND is_active = TRUE
            GROUP BY type, severity
            ORDER BY
                CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
                count DESC
        """),
        {"cutoff": cutoff},
    )
    alert_groups = result.mappings().all()

    if not alert_groups:
        logger.info("No alerts in last 24h, skipping digest")
        return {"sent": 0}

    # Build summary text
    total_alerts = sum(g["count"] for g in alert_groups)
    critical_count = sum(g["count"] for g in alert_groups if g["severity"] == "critical")
    warning_count = sum(g["count"] for g in alert_groups if g["severity"] == "warning")

    sections = []
    for g in alert_groups:
        commodities = ", ".join(g["commodities"][:5]) if g["commodities"] else "N/A"
        sections.append(
            f"  [{g['severity'].upper()}] {g['type']}: {g['count']} alerts (commodities: {commodities})"
        )

    summary_text = (
        f"SupplyShock Daily Digest - {datetime.utcnow().strftime('%Y-%m-%d')}\n\n"
        f"Total alerts: {total_alerts} "
        f"({critical_count} critical, {warning_count} warning)\n\n"
        + "\n".join(sections)
    )

    summary_html = f"""
    <h2>SupplyShock Daily Digest</h2>
    <p><strong>{datetime.utcnow().strftime('%Y-%m-%d')}</strong></p>
    <p>Total alerts: <strong>{total_alerts}</strong>
       ({critical_count} critical, {warning_count} warning)</p>
    <table style="border-collapse:collapse;width:100%">
      <tr style="background:#1a1a2e;color:white">
        <th style="padding:8px;text-align:left">Severity</th>
        <th style="padding:8px;text-align:left">Type</th>
        <th style="padding:8px;text-align:right">Count</th>
        <th style="padding:8px;text-align:left">Commodities</th>
      </tr>
      {"".join(
        f'<tr style="border-bottom:1px solid #eee">'
        f'<td style="padding:8px"><span style="color:{"#ef4444" if g["severity"]=="critical" else "#f59e0b" if g["severity"]=="warning" else "#6b7280"}">'
        f'{g["severity"].upper()}</span></td>'
        f'<td style="padding:8px">{g["type"]}</td>'
        f'<td style="padding:8px;text-align:right">{g["count"]}</td>'
        f'<td style="padding:8px">{", ".join(g["commodities"][:5]) if g["commodities"] else "N/A"}</td></tr>'
        for g in alert_groups
      )}
    </table>
    """

    # Get users who have email digest enabled
    users_result = await db.execute(
        text("""
            SELECT DISTINCT u.email, u.name
            FROM users u
            JOIN alert_subscriptions s ON s.user_id = u.clerk_id
            WHERE s.notify_email = TRUE AND u.email IS NOT NULL
        """)
    )
    users = users_result.mappings().all()

    sent = 0
    for user in users:
        try:
            await send_email(
                to=user["email"],
                subject=f"SupplyShock Daily Digest: {total_alerts} alerts ({critical_count} critical)",
                html=summary_html,
                text=summary_text,
            )
            sent += 1
        except Exception as e:
            logger.error(f"Failed to send digest to {user['email']}: {e}")

    logger.info(f"Daily digest sent to {sent}/{len(users)} users")
    return {"sent": sent, "total_users": len(users), "total_alerts": total_alerts}
