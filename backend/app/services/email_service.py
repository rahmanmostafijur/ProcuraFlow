import logging
import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models.email import OUTBOX_FAILED, OUTBOX_LOGGED, OUTBOX_QUEUED, OUTBOX_SENT, EmailOutbox, EmailTemplate
from app.services.email_templates import TEMPLATES, render_template

logger = logging.getLogger(__name__)

SMTP_TIMEOUT_SECONDS = 20
MAX_ERROR_LENGTH = 500
DELIVERY_BATCH_SIZE = 50


async def _template_text(db: AsyncSession, key: str) -> tuple[str, str]:
    """The edited template when there is one, otherwise the built-in default."""
    row = (await db.execute(select(EmailTemplate).where(EmailTemplate.key == key))).scalar_one_or_none()
    if row is not None:
        return row.subject, row.body
    default = TEMPLATES[key]
    return default.subject, default.body


async def queue_email(db: AsyncSession, to_address: str, template_key: str, context: dict[str, str]) -> EmailOutbox:
    """Render a template and add it to the outbox in the caller's transaction (no commit here)."""
    subject_source, body_source = await _template_text(db, template_key)
    subject, body = render_template(template_key, subject_source, body_source, context)
    message = EmailOutbox(
        to_address=to_address, subject=subject, body=body, template_key=template_key, status=OUTBOX_QUEUED
    )
    db.add(message)
    return message


def _build_message(settings: Settings, row: EmailOutbox) -> EmailMessage:
    message = EmailMessage()
    message["From"] = settings.email_from
    message["To"] = row.to_address
    message["Subject"] = row.subject
    message.set_content(row.body)
    return message


def _send_smtp(settings: Settings, host: str, message: EmailMessage) -> None:
    with smtplib.SMTP(host, settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS) as smtp:
        if settings.smtp_starttls:
            smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


def deliver(settings: Settings, row: EmailOutbox) -> None:
    """Attempt one delivery and record the outcome on the row. Never raises for a delivery problem."""
    row.attempts += 1
    if not settings.smtp_host:
        logger.info("Email (not sent, SMTP not configured) to=%s subject=%s", row.to_address, row.subject)
        row.status = OUTBOX_LOGGED
        row.sent_at = datetime.now(UTC)
        return
    try:
        _send_smtp(settings, settings.smtp_host, _build_message(settings, row))
    except (OSError, smtplib.SMTPException) as exc:
        row.last_error = str(exc)[:MAX_ERROR_LENGTH]
        row.status = OUTBOX_FAILED if row.attempts >= settings.email_max_attempts else OUTBOX_QUEUED
        logger.warning("Email %s delivery failed (attempt %s): %s", row.id, row.attempts, exc)
        return
    row.status = OUTBOX_SENT
    row.last_error = None
    row.sent_at = datetime.now(UTC)


async def deliver_queued(db: AsyncSession, settings: Settings | None = None) -> int:
    """Deliver queued messages, oldest first. Returns how many were attempted."""
    settings = settings or get_settings()
    rows = (
        (
            await db.execute(
                select(EmailOutbox)
                .where(EmailOutbox.status == OUTBOX_QUEUED)
                .order_by(EmailOutbox.id)
                .limit(DELIVERY_BATCH_SIZE)
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    for row in rows:
        deliver(settings, row)
    await db.commit()
    return len(rows)
