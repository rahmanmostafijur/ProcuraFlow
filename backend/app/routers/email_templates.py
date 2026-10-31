from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.deps import DbSession, require_permission
from app.models.email import EmailTemplate
from app.models.user import User
from app.services.audit_service import record_audit_event
from app.services.email_templates import TEMPLATES, TemplateRenderError, validate_template

router = APIRouter(prefix="/email-templates", tags=["email-templates"])

RequireSettingsManage = Annotated[User, Depends(require_permission("settings:manage"))]


class TemplateWrite(BaseModel):
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=10_000)


class TemplateRead(BaseModel):
    key: str
    label: str
    variables: list[str]
    subject: str
    body: str
    is_customised: bool
    default_subject: str
    default_body: str


async def _edited(db: DbSession) -> dict[str, EmailTemplate]:
    rows = (await db.execute(select(EmailTemplate))).scalars().all()
    return {row.key: row for row in rows}


def _read(key: str, edited: EmailTemplate | None) -> TemplateRead:
    definition = TEMPLATES[key]
    return TemplateRead(
        key=key,
        label=definition.label,
        variables=list(definition.variables),
        subject=edited.subject if edited else definition.subject,
        body=edited.body if edited else definition.body,
        is_customised=edited is not None,
        default_subject=definition.subject,
        default_body=definition.body,
    )


def _known_key(key: str) -> str:
    if key not in TEMPLATES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return key


@router.get("", response_model=list[TemplateRead])
async def list_templates(db: DbSession, _: RequireSettingsManage) -> list[TemplateRead]:
    edited = await _edited(db)
    return [_read(key, edited.get(key)) for key in TEMPLATES]


@router.put("/{key}", response_model=TemplateRead)
async def save_template(
    key: str, payload: TemplateWrite, db: DbSession, current_user: RequireSettingsManage
) -> TemplateRead:
    _known_key(key)
    try:
        validate_template(key, payload.subject, payload.body)
    except TemplateRenderError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    row = (await _edited(db)).get(key)
    if row is None:
        row = EmailTemplate(key=key, subject=payload.subject, body=payload.body)
        db.add(row)
    else:
        row.subject = payload.subject
        row.body = payload.body
    await record_audit_event(
        db,
        user_id=current_user.id,
        action="email_template_saved",
        entity_type="email_template",
        extra_data={"key": key},
    )
    await db.commit()
    return _read(key, row)


@router.delete("/{key}", response_model=TemplateRead)
async def reset_template(key: str, db: DbSession, current_user: RequireSettingsManage) -> TemplateRead:
    """Back to the built-in text."""
    _known_key(key)
    row = (await _edited(db)).get(key)
    if row is not None:
        await db.delete(row)
        await record_audit_event(
            db,
            user_id=current_user.id,
            action="email_template_reset",
            entity_type="email_template",
            extra_data={"key": key},
        )
        await db.commit()
    return _read(key, None)
