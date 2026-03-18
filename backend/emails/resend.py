"""Email sending via Resend API with Jinja2 templates.

Usage:
    from emails.resend import send_email
    await send_email("welcome_pro", "user@example.com", {"name": "John"})
"""

import logging
from pathlib import Path

import resend
from jinja2 import Environment, FileSystemLoader

from config import settings

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)

FROM_EMAIL = "SupplyShock <noreply@supplyshock.io>"

# Subject lines per template
SUBJECTS: dict[str, str] = {
    "welcome_pro": "Welcome to SupplyShock Pro!",
    "payment_failed": "Payment failed — action required",
    "critical_alert": "Critical Supply Chain Alert",
    "plan_downgraded": "Your plan has been downgraded",
    "alert_notification": "SupplyShock Alert Notification",
}


async def send_email(
    template_name: str,
    to_email: str,
    context: dict | None = None,
    subject: str | None = None,
) -> str | None:
    """Render Jinja2 template and send via Resend.

    Returns Resend email ID on success, None on failure.
    """
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set — skipping email %s to %s", template_name, to_email)
        return None

    resend.api_key = settings.RESEND_API_KEY

    try:
        template = _jinja_env.get_template(f"{template_name}.html")
    except Exception:
        logger.error("Email template not found: %s", template_name)
        return None

    html = template.render(**(context or {}))
    email_subject = subject or SUBJECTS.get(template_name, "SupplyShock Notification")

    try:
        result = resend.Emails.send({
            "from": FROM_EMAIL,
            "to": [to_email],
            "subject": email_subject,
            "html": html,
        })
        email_id = result.get("id") if isinstance(result, dict) else getattr(result, "id", None)
        logger.info("Email sent: %s to %s (id=%s)", template_name, to_email, email_id)
        return email_id
    except Exception as e:
        logger.error("Failed to send email %s to %s: %s", template_name, to_email, e)
        return None
