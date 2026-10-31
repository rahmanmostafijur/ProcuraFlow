"""A person's personal data as one JSON document (the GDPR right of access). Every export is audited."""

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.attachment import Attachment
from app.models.audit import AuditLog
from app.models.email import EmailOutbox
from app.models.notification import Notification
from app.models.payment import PaymentRun
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_request import PurchaseRequest
from app.models.refresh_token import RefreshToken
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice
from app.models.user import User
from app.services.audit_service import record_audit_event, to_json_safe


def _audit_row(entry: AuditLog) -> dict[str, Any]:
    return {
        "id": entry.id,
        "action": entry.action,
        "entity_type": entry.entity_type,
        "entity_id": entry.entity_id,
        "details": entry.extra_data,
        "created_at": entry.created_at,
    }


async def _ids(db: AsyncSession, column: Any, owner_column: Any, user_id: int) -> list[int]:
    return list((await db.execute(select(column).where(owner_column == user_id).order_by(column))).scalars().all())


async def _emails_to(db: AsyncSession, address: str) -> list[dict[str, Any]]:
    rows = (
        (
            await db.execute(
                select(EmailOutbox)
                .where(func.lower(EmailOutbox.to_address) == address.lower())
                .order_by(EmailOutbox.id)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "subject": row.subject,
            "template": row.template_key,
            "status": row.status,
            "created_at": row.created_at,
            "sent_at": row.sent_at,
        }
        for row in rows
    ]


async def _user_data(db: AsyncSession, user: User) -> dict[str, Any]:
    """Everything stored about one account. The password hash is never included."""
    audit = (
        (
            await db.execute(
                select(AuditLog)
                .where(
                    or_(AuditLog.user_id == user.id, (AuditLog.entity_type == "user") & (AuditLog.entity_id == user.id))
                )
                .order_by(AuditLog.id)
            )
        )
        .scalars()
        .all()
    )
    notifications = (
        (await db.execute(select(Notification).where(Notification.user_id == user.id).order_by(Notification.id)))
        .scalars()
        .all()
    )
    attachments = (
        (await db.execute(select(Attachment).where(Attachment.uploaded_by == user.id).order_by(Attachment.id)))
        .scalars()
        .all()
    )
    sessions = await db.scalar(select(func.count()).select_from(RefreshToken).where(RefreshToken.user_id == user.id))
    return {
        "profile": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.name,
            "is_active": user.is_active,
            "supplier_id": user.supplier_id,
            "created_at": user.created_at,
        },
        "sessions_issued": sessions or 0,
        "notifications": [
            {"message": row.message, "is_read": row.is_read, "created_at": row.created_at} for row in notifications
        ],
        "audit_entries": [_audit_row(entry) for entry in audit],
        "attachments_uploaded": [
            {"id": row.id, "filename": row.filename, "parent_type": row.parent_type, "parent_id": row.parent_id}
            for row in attachments
        ],
        "emails_sent_to_user": await _emails_to(db, user.email),
        # Documents the person created are business records and stay; they are listed so the person can see them.
        "records_created": {
            "purchase_requests": await _ids(db, PurchaseRequest.id, PurchaseRequest.requester_id, user.id),
            "purchase_orders": await _ids(db, PurchaseOrder.id, PurchaseOrder.created_by, user.id),
            "supplier_invoices": await _ids(db, SupplierInvoice.id, SupplierInvoice.created_by, user.id),
            "payment_runs": await _ids(db, PaymentRun.id, PaymentRun.created_by, user.id),
        },
    }


def _document(subject: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    return to_json_safe({"generated_at": datetime.now(UTC), "subject": subject} | data)  # type: ignore[no-any-return]


async def export_user(db: AsyncSession, actor: User, user_id: int) -> dict[str, Any]:
    user = await db.scalar(select(User).options(selectinload(User.role)).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    data = await _user_data(db, user)
    await record_audit_event(db, user_id=actor.id, action="gdpr_exported", entity_type="user", entity_id=user.id)
    await db.commit()
    return _document({"type": "user", "id": user.id}, data)


async def export_supplier_contact(db: AsyncSession, actor: User, supplier_id: int) -> dict[str, Any]:
    supplier = await db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    portal_users = (
        (
            await db.execute(
                select(User).options(selectinload(User.role)).where(User.supplier_id == supplier_id).order_by(User.id)
            )
        )
        .scalars()
        .all()
    )
    data = {
        "contact": {
            "supplier_name": supplier.name,
            "contact_name": supplier.contact_name,
            "email": supplier.email,
            "phone": supplier.phone,
        },
        "emails_sent_to_contact": await _emails_to(db, supplier.email) if supplier.email else [],
        "portal_accounts": [await _user_data(db, user) for user in portal_users],
    }
    await record_audit_event(
        db, user_id=actor.id, action="gdpr_exported", entity_type="supplier", entity_id=supplier.id
    )
    await db.commit()
    return _document({"type": "supplier_contact", "id": supplier.id}, data)
