"""Anonymising a person without touching the financial record.

The user row stays (purchase orders, invoices, approvals and payments point at it), but the name and email become
irreversible placeholders, the account is closed and its sessions are revoked. The person's name and email are also
removed from the audit entries about them; the entries themselves stay. Running it again changes nothing.
"""

import secrets
from collections.abc import Mapping, Sequence
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password
from app.models.audit import AuditLog
from app.models.email import EmailOutbox, UserToken
from app.models.notification import Notification
from app.models.role import Role
from app.models.supplier import Supplier
from app.models.user import User
from app.services.audit_service import record_audit_event
from app.services.gdpr_redaction import REDACTED, redact_json
from app.services.refresh_token_service import revoke_all_sessions

# A reserved domain (RFC 2606) that passes email validation but can never belong to a real mailbox.
ANONYMISED_DOMAIN = "anonymised.example.com"
ANONYMISED_NAME = "Anonymised user"
ANONYMISED_CONTACT = "Anonymised contact"
ADMIN_ROLE = "admin"


def is_anonymised_user(user: User) -> bool:
    return user.email.endswith(f"@{ANONYMISED_DOMAIN}")


def _earlier_values(entries: Sequence[AuditLog], tracked_fields: Mapping[str, str]) -> dict[str, str]:
    """Values the tracked fields held before (``changes`` entries record from/to), mapped to their replacement.

    The current value is not enough: an entry written after a rename still names the old one.
    """
    found: dict[str, str] = {}
    for entry in entries:
        changes = (entry.extra_data or {}).get("changes")
        if not isinstance(changes, dict):
            continue
        for field, replacement in tracked_fields.items():
            change = changes.get(field)
            if isinstance(change, dict):
                for side in ("from", "to"):
                    value = change.get(side)
                    if isinstance(value, str) and value:
                        found[value] = replacement
    return found


async def _redact_audit_entries(
    db: AsyncSession, entity_type: str, entity_id: int, needles: dict[str, str], tracked_fields: Mapping[str, str]
) -> int:
    entries = (
        (await db.execute(select(AuditLog).where(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)))
        .scalars()
        .all()
    )
    needles = _earlier_values(entries, tracked_fields) | needles
    changed = 0
    for entry in entries:
        if entry.extra_data is None:
            continue
        redacted = redact_json(entry.extra_data, needles)
        if redacted != entry.extra_data:
            entry.extra_data = redacted  # a new object, so the JSONB column is seen as changed
            changed += 1
    return changed


async def _redact_emails_to(db: AsyncSession, address: str) -> int:
    result = await db.execute(
        update(EmailOutbox)
        .where(func.lower(EmailOutbox.to_address) == address.lower())
        .values(to_address=f"redacted@{ANONYMISED_DOMAIN}", subject=REDACTED, body=REDACTED)
    )
    return result.rowcount


async def _ensure_not_last_admin(db: AsyncSession, user: User) -> None:
    if user.role.name != ADMIN_ROLE or not user.is_active:
        return
    others = await db.scalar(
        select(func.count())
        .select_from(User)
        .join(Role, Role.id == User.role_id)
        .where(Role.name == ADMIN_ROLE, User.is_active.is_(True), User.id != user.id)
    )
    if not others:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This is the last active administrator; make another user an administrator first",
        )


async def anonymise_account(db: AsyncSession, user: User) -> dict[str, int]:
    """Anonymise one user row and what is stored about them. Does not commit and does not write the audit event."""
    needles = {user.email: f"{REDACTED}@{ANONYMISED_DOMAIN}", user.full_name: ANONYMISED_NAME}
    old_email = user.email
    user.email = f"anonymised-user-{user.id}@{ANONYMISED_DOMAIN}"
    user.full_name = ANONYMISED_NAME
    # Nobody knows this password, and the account is closed as well.
    user.hashed_password = hash_password(secrets.token_urlsafe(32))
    user.is_active = False
    sessions = await revoke_all_sessions(db, user.id)
    await db.execute(delete(UserToken).where(UserToken.user_id == user.id))
    notifications = await db.execute(delete(Notification).where(Notification.user_id == user.id))
    return {
        "sessions_revoked": sessions,
        "notifications_deleted": notifications.rowcount,
        "emails_redacted": await _redact_emails_to(db, old_email),
        "audit_entries_redacted": await _redact_audit_entries(
            db, "user", user.id, needles, {"full_name": ANONYMISED_NAME, "email": f"{REDACTED}@{ANONYMISED_DOMAIN}"}
        ),
    }


async def _load_user(db: AsyncSession, user_id: int) -> User:
    user = await db.scalar(select(User).options(selectinload(User.role)).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


async def anonymise_user(db: AsyncSession, actor: User, user_id: int) -> dict[str, Any]:
    user = await _load_user(db, user_id)
    if is_anonymised_user(user):
        return {"user_id": user.id, "already_anonymised": True}
    await _ensure_not_last_admin(db, user)
    summary = await anonymise_account(db, user)
    await record_audit_event(
        db, user_id=actor.id, action="user_anonymised", entity_type="user", entity_id=user.id, extra_data=summary
    )
    await db.commit()
    return {"user_id": user.id, "already_anonymised": False, **summary}


async def anonymise_supplier_contact(db: AsyncSession, actor: User, supplier_id: int) -> dict[str, Any]:
    """Clear the supplier's contact person (name, email, phone) and anonymise the portal accounts of the supplier.

    The supplier itself, its orders, invoices and payments, and its business address and tax number are kept.
    """
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
    pending_users = [user for user in portal_users if not is_anonymised_user(user)]
    has_contact = any((supplier.contact_name, supplier.email, supplier.phone))
    if not pending_users and (not has_contact or supplier.contact_name == ANONYMISED_CONTACT):
        return {"supplier_id": supplier.id, "already_anonymised": True}

    needles = {
        value: ANONYMISED_CONTACT if value == supplier.contact_name else f"{REDACTED}@{ANONYMISED_DOMAIN}"
        for value in (supplier.contact_name, supplier.email, supplier.phone)
        if value
    }
    emails = await _redact_emails_to(db, supplier.email) if supplier.email else 0
    redacted_email = f"{REDACTED}@{ANONYMISED_DOMAIN}"
    audit_entries = await _redact_audit_entries(
        db,
        "supplier",
        supplier.id,
        needles,
        {"contact_name": ANONYMISED_CONTACT, "email": redacted_email, "phone": redacted_email},
    )
    supplier.contact_name = ANONYMISED_CONTACT
    supplier.email = None
    supplier.phone = None
    accounts = [await anonymise_account(db, user) for user in pending_users]
    summary = {
        "portal_accounts_anonymised": len(accounts),
        "emails_redacted": emails + sum(account["emails_redacted"] for account in accounts),
        "audit_entries_redacted": audit_entries + sum(account["audit_entries_redacted"] for account in accounts),
    }
    await record_audit_event(
        db,
        user_id=actor.id,
        action="supplier_contact_anonymised",
        entity_type="supplier",
        entity_id=supplier.id,
        extra_data=summary,
    )
    await db.commit()
    return {"supplier_id": supplier.id, "already_anonymised": False, **summary}
