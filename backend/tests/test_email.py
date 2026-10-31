import smtplib
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.email import OUTBOX_FAILED, OUTBOX_LOGGED, OUTBOX_QUEUED, OUTBOX_SENT, EmailOutbox, EmailTemplate
from app.services.email_service import deliver, deliver_queued, queue_email
from app.services.email_templates import TEMPLATES, TemplateRenderError, render_template, validate_template

RESET_CONTEXT = {"full_name": "Ada Lovelace", "link": "https://app.example/reset?t=abc", "expires_in": "30 minutes"}


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {"jwt_secret_key": "x" * 40, "environment": "test"}
    return Settings(**(base | overrides))  # type: ignore[arg-type]


def test_every_default_template_validates_and_renders() -> None:
    for definition in TEMPLATES.values():
        context = {name: "value" for name in definition.variables}
        subject, body = render_template(definition.key, definition.subject, definition.body, context)
        assert subject
        assert body


def test_unknown_variable_is_rejected_on_save() -> None:
    with pytest.raises(TemplateRenderError, match="Unknown variables: secret"):
        validate_template("password_reset", "Hi", "{{ secret }}")


def test_syntax_error_is_rejected_on_save() -> None:
    with pytest.raises(TemplateRenderError, match="syntax"):
        validate_template("password_reset", "Hi", "{% if %}")


def test_sandbox_blocks_attribute_escapes() -> None:
    body = "{{ full_name.__class__.__mro__ }}"
    with pytest.raises(TemplateRenderError):
        render_template("password_reset", "Hi", body, RESET_CONTEXT)


def test_subject_newlines_cannot_inject_headers() -> None:
    context = RESET_CONTEXT | {"full_name": "Ada\r\nBcc: evil@example.com"}
    subject, _ = render_template("invitation", "Hi {{ full_name }}", "x", context | {"company_name": "c", "link": "l"})
    assert "\n" not in subject
    assert "\r" not in subject


def test_multiline_subject_template_is_rejected() -> None:
    with pytest.raises(TemplateRenderError, match="single line"):
        validate_template("password_reset", "Hi\nBcc: x", "body")


async def test_queue_email_uses_default_template(db_session: AsyncSession) -> None:
    message = await queue_email(db_session, "ada@example.com", "password_reset", RESET_CONTEXT)
    await db_session.commit()
    assert message.status == OUTBOX_QUEUED
    assert "Ada Lovelace" in message.body
    assert message.attempts == 0


async def test_queue_email_prefers_an_edited_template(db_session: AsyncSession) -> None:
    db_session.add(EmailTemplate(key="password_reset", subject="Custom {{ full_name }}", body="Go: {{ link }}"))
    await db_session.commit()
    message = await queue_email(db_session, "ada@example.com", "password_reset", RESET_CONTEXT)
    assert message.subject == "Custom Ada Lovelace"
    assert message.body == "Go: https://app.example/reset?t=abc"


async def test_without_smtp_host_messages_are_logged_not_sent(db_session: AsyncSession) -> None:
    await queue_email(db_session, "ada@example.com", "password_reset", RESET_CONTEXT)
    await db_session.commit()
    with patch("app.services.email_service.smtplib.SMTP") as smtp:
        attempted = await deliver_queued(db_session, _settings())
    smtp.assert_not_called()
    row = (await db_session.execute(select(EmailOutbox))).scalar_one()
    assert attempted == 1
    assert row.status == OUTBOX_LOGGED
    assert row.attempts == 1


async def test_successful_smtp_delivery_marks_sent(db_session: AsyncSession) -> None:
    row = await queue_email(db_session, "ada@example.com", "password_reset", RESET_CONTEXT)
    with patch("app.services.email_service.smtplib.SMTP") as smtp:
        deliver(_settings(smtp_host="mail.example.com", smtp_username="u", smtp_password="p"), row)
    server = smtp.return_value.__enter__.return_value
    server.starttls.assert_called_once()
    server.login.assert_called_once_with("u", "p")
    server.send_message.assert_called_once()
    assert row.status == OUTBOX_SENT
    assert row.sent_at is not None


async def test_failed_delivery_is_retried_then_given_up(db_session: AsyncSession) -> None:
    row = await queue_email(db_session, "ada@example.com", "password_reset", RESET_CONTEXT)
    settings = _settings(smtp_host="mail.example.com", email_max_attempts=2)
    with patch("app.services.email_service.smtplib.SMTP", side_effect=smtplib.SMTPException("boom")):
        deliver(settings, row)
        assert row.status == OUTBOX_QUEUED
        assert row.last_error == "boom"
        deliver(settings, row)
    assert row.status == OUTBOX_FAILED
    assert row.attempts == 2
