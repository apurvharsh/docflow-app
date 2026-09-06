"""SMTP delivery for selected application notifications."""

import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)


def email_notifications_configured() -> bool:
    return bool(
        settings.email_notifications_enabled
        and settings.smtp_host
        and settings.smtp_username
        and settings.smtp_password
        and settings.email_from
    )


def send_notification_email(recipient: str, subject: str, body: str) -> None:
    """Send one notification email, or log why delivery is unavailable."""
    if not email_notifications_configured():
        logger.info("Email notification skipped: SMTP is not configured")
        return

    message = EmailMessage()
    message["From"] = settings.email_from
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            if settings.smtp_use_tls:
                server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException):
        logger.exception("Email notification delivery failed for %s", recipient)
