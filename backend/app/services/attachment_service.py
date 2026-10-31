"""Files attached to records. Who may see or change a file is decided by the record it hangs off, never by the file."""

import hashlib
import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import PurePath

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import has_permission
from app.core.file_types import ATTACHMENT_KINDS, detect_file_type
from app.models.attachment import Attachment
from app.models.enums import AttachmentParentType, InvoiceStatus, PurchaseRequestStatus
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_request import PurchaseRequest
from app.models.supplier_invoice import SupplierInvoice
from app.models.user import User
from app.schemas.attachment import AttachmentRead
from app.schemas.person import PersonRead
from app.services import invoice_access
from app.services.audit_service import record_audit_event
from app.services.purchase_request_service import get_request
from app.storage import StorageBackend, StoredObjectNotFoundError

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_ATTACHMENTS_PER_RECORD = 20
MAX_FILENAME_LENGTH = 255

_UNSAFE_FILENAME = re.compile(r"[\x00-\x1f\x7f/\\]")


def _unsupported_message(allowed_kinds: frozenset[str]) -> str:
    labels = {"pdf": "PDF", "png": "PNG", "jpg": "JPEG", "xlsx": "Excel (.xlsx)", "csv": "CSV"}
    names = [label for kind, label in labels.items() if kind in allowed_kinds]
    if len(names) == 1:
        return f"Attach a {names[0]} file."
    return f"Attach a {', '.join(names[:-1])} or {names[-1]} file."


def clean_filename(name: str | None) -> str:
    """A display name: no directories, no control characters, never empty, never longer than the column."""
    base = PurePath((name or "").replace("\\", "/")).name
    base = _UNSAFE_FILENAME.sub("", base).strip().strip(".")
    return (base or "file")[:MAX_FILENAME_LENGTH]


Check = Callable[[AsyncSession, User, int], Awaitable[bool]]


@dataclass(frozen=True)
class ParentPolicy:
    can_read: Check
    can_write: Check


async def _request_readable(db: AsyncSession, user: User, parent_id: int) -> bool:
    try:
        await get_request(db, parent_id, user)
    except HTTPException:
        return False
    return True


async def _request_writable(db: AsyncSession, user: User, parent_id: int) -> bool:
    request = await db.get(PurchaseRequest, parent_id)
    return (
        request is not None
        and request.requester_id == user.id
        and request.status
        in (PurchaseRequestStatus.DRAFT, PurchaseRequestStatus.REJECTED, PurchaseRequestStatus.SUBMITTED)
    )


async def _order_readable(db: AsyncSession, user: User, parent_id: int) -> bool:
    return await db.get(PurchaseOrder, parent_id) is not None


async def _order_writable(db: AsyncSession, user: User, parent_id: int) -> bool:
    return has_permission(user, "po:create") and await _order_readable(db, user, parent_id)


INVOICE_ATTACHABLE_STATUSES = (InvoiceStatus.DRAFT, InvoiceStatus.EXCEPTION, InvoiceStatus.ON_HOLD)


async def _invoice_readable(db: AsyncSession, user: User, parent_id: int) -> bool:
    invoice = await db.get(SupplierInvoice, parent_id)
    return invoice is not None and await invoice_access.can_view(db, invoice, user)


async def _invoice_writable(db: AsyncSession, user: User, parent_id: int) -> bool:
    invoice = await db.get(SupplierInvoice, parent_id)
    return (
        invoice is not None
        and has_permission(user, "invoice:write")
        and invoice_access.can_modify(invoice, user)
        and invoice.status in INVOICE_ATTACHABLE_STATUSES
    )


POLICIES: dict[AttachmentParentType, ParentPolicy] = {
    AttachmentParentType.PURCHASE_REQUEST: ParentPolicy(_request_readable, _request_writable),
    AttachmentParentType.PURCHASE_ORDER: ParentPolicy(_order_readable, _order_writable),
    AttachmentParentType.SUPPLIER_INVOICE: ParentPolicy(_invoice_readable, _invoice_writable),
}


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")


async def _ensure_readable(db: AsyncSession, user: User, parent_type: AttachmentParentType, parent_id: int) -> None:
    """A parent the user cannot see is reported as missing, so attachment lists cannot be used to probe ids."""
    if not await POLICIES[parent_type].can_read(db, user, parent_id):
        raise _not_found()


def to_read(attachment: Attachment, uploader: User) -> AttachmentRead:
    return AttachmentRead(
        id=attachment.id,
        parent_type=attachment.parent_type,
        parent_id=attachment.parent_id,
        filename=attachment.filename,
        content_type=attachment.content_type,
        size_bytes=attachment.size_bytes,
        uploaded_by=PersonRead(id=uploader.id, full_name=uploader.full_name),
        created_at=attachment.created_at,
    )


async def list_attachments(
    db: AsyncSession, viewer: User, parent_type: AttachmentParentType, parent_id: int
) -> list[AttachmentRead]:
    await _ensure_readable(db, viewer, parent_type, parent_id)
    rows = (
        await db.execute(
            select(Attachment, User)
            .join(User, User.id == Attachment.uploaded_by)
            .where(Attachment.parent_type == parent_type, Attachment.parent_id == parent_id)
            .order_by(Attachment.id)
        )
    ).all()
    return [to_read(attachment, uploader) for attachment, uploader in rows]


async def upload_attachment(
    db: AsyncSession,
    storage: StorageBackend,
    actor: User,
    parent_type: AttachmentParentType,
    parent_id: int,
    filename: str | None,
    data: bytes,
) -> AttachmentRead:
    await _ensure_readable(db, actor, parent_type, parent_id)
    if not await POLICIES[parent_type].can_write(db, actor, parent_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot attach files to this record")
    return await store_attachment(db, storage, actor, parent_type, parent_id, filename, data, ATTACHMENT_KINDS)


async def store_attachment(
    db: AsyncSession,
    storage: StorageBackend,
    actor: User,
    parent_type: AttachmentParentType,
    parent_id: int,
    filename: str | None,
    data: bytes,
    allowed_kinds: frozenset[str],
) -> AttachmentRead:
    """Validate the bytes by content, store the file and record it. The caller has already checked access."""
    detected = detect_file_type(data, allowed_kinds)
    if detected is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=_unsupported_message(allowed_kinds)
        )
    count = await db.scalar(
        select(func.count())
        .select_from(Attachment)
        .where(Attachment.parent_type == parent_type, Attachment.parent_id == parent_id)
    )
    if (count or 0) >= MAX_ATTACHMENTS_PER_RECORD:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A record can have at most {MAX_ATTACHMENTS_PER_RECORD} attachments",
        )

    content_type, extension = detected
    storage_key = f"attachments/{uuid.uuid4().hex}.{extension}"
    await storage.save(storage_key, data, content_type)
    attachment = Attachment(
        parent_type=parent_type,
        parent_id=parent_id,
        filename=clean_filename(filename),
        content_type=content_type,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        storage_key=storage_key,
        uploaded_by=actor.id,
    )
    db.add(attachment)
    await db.flush()
    await record_audit_event(
        db,
        user_id=actor.id,
        action="attachment_uploaded",
        entity_type=parent_type.value,
        entity_id=parent_id,
        extra_data={"attachment_id": attachment.id, "filename": attachment.filename, "bytes": len(data)},
    )
    try:
        await db.commit()
    except Exception:
        await storage.delete(storage_key)
        raise
    await db.refresh(attachment)
    return to_read(attachment, actor)


async def _get_visible(db: AsyncSession, viewer: User, attachment_id: int) -> Attachment:
    attachment = await db.get(Attachment, attachment_id)
    if attachment is None:
        raise _not_found()
    await _ensure_readable(db, viewer, attachment.parent_type, attachment.parent_id)
    return attachment


async def read_attachment(
    db: AsyncSession, storage: StorageBackend, viewer: User, attachment_id: int
) -> tuple[Attachment, bytes]:
    attachment = await _get_visible(db, viewer, attachment_id)
    try:
        return attachment, await storage.read(attachment.storage_key)
    except StoredObjectNotFoundError as exc:
        raise _not_found() from exc


async def delete_attachment(db: AsyncSession, storage: StorageBackend, actor: User, attachment_id: int) -> None:
    attachment = await _get_visible(db, actor, attachment_id)
    if not await POLICIES[attachment.parent_type].can_write(db, actor, attachment.parent_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot remove files from this record")
    await record_audit_event(
        db,
        user_id=actor.id,
        action="attachment_removed",
        entity_type=attachment.parent_type.value,
        entity_id=attachment.parent_id,
        extra_data={"attachment_id": attachment.id, "filename": attachment.filename},
    )
    storage_key = attachment.storage_key
    await db.delete(attachment)
    await db.commit()
    # The record is gone either way; a file that cannot be deleted is an orphan, not a visible attachment.
    await storage.delete(storage_key)
