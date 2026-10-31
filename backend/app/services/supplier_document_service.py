"""Supplier compliance documents (W-9, VAT certificate, insurance, ISO, bank letter) and their expiry.

The expiry status is never stored. ``document_status`` works it out from the expiry date and the date it is given,
every time a document is read, so a document changes from valid to expiring soon to expired without any job having
to run, and a test can pin "today" to any day.

Both the internal screens and the supplier portal use these functions; the portal passes the supplier id of the
signed-in supplier account, never one taken from the request.
"""

import hashlib
from dataclasses import dataclass
from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.file_types import DOCUMENT_KINDS, detect_file_type
from app.models.enums import SupplierDocumentStatus, SupplierDocumentType
from app.models.supplier import Supplier
from app.models.supplier_document import SupplierDocument
from app.models.user import User
from app.schemas.person import PersonRead
from app.schemas.supplier_document import ExpiringDocumentRead, SupplierDocumentRead
from app.services.attachment_service import clean_filename
from app.services.audit_service import record_audit_event
from app.storage import StorageBackend, StoredObjectNotFoundError, new_storage_key

EXPIRING_SOON_DAYS = 30
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
MAX_DOCUMENTS_PER_SUPPLIER = 50
DOCUMENT_LABELS = {
    SupplierDocumentType.W9: "W-9",
    SupplierDocumentType.VAT_CERTIFICATE: "VAT certificate",
    SupplierDocumentType.INSURANCE: "Insurance certificate",
    SupplierDocumentType.ISO_CERTIFICATE: "ISO certificate",
    SupplierDocumentType.BANK_LETTER: "Bank letter",
}


def document_status(expiry_date: date | None, today: date) -> SupplierDocumentStatus:
    """A document with no expiry date never expires. One that expires today is still valid today but expiring."""
    if expiry_date is None:
        return SupplierDocumentStatus.VALID
    if expiry_date < today:
        return SupplierDocumentStatus.EXPIRED
    if expiry_date <= today + timedelta(days=EXPIRING_SOON_DAYS):
        return SupplierDocumentStatus.EXPIRING_SOON
    return SupplierDocumentStatus.VALID


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")


def to_read(document: SupplierDocument, uploader: User, today: date) -> SupplierDocumentRead:
    expiry = document.expiry_date
    return SupplierDocumentRead(
        id=document.id,
        supplier_id=document.supplier_id,
        document_type=SupplierDocumentType(document.document_type),
        issue_date=document.issue_date,
        expiry_date=expiry,
        status=document_status(expiry, today),
        days_until_expiry=(expiry - today).days if expiry else None,
        filename=document.filename,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        uploaded_by=PersonRead(id=uploader.id, full_name=uploader.full_name),
        created_at=document.created_at,
    )


async def ensure_supplier_exists(db: AsyncSession, supplier_id: int) -> Supplier:
    supplier = await db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    return supplier


async def list_documents(db: AsyncSession, supplier_id: int, today: date) -> list[SupplierDocumentRead]:
    await ensure_supplier_exists(db, supplier_id)
    rows = (
        await db.execute(
            select(SupplierDocument, User)
            .join(User, User.id == SupplierDocument.uploaded_by)
            .where(SupplierDocument.supplier_id == supplier_id)
            .order_by(SupplierDocument.document_type, SupplierDocument.id)
        )
    ).all()
    return [to_read(document, uploader, today) for document, uploader in rows]


async def get_document(db: AsyncSession, supplier_id: int, document_id: int) -> SupplierDocument:
    """The document only if it belongs to this supplier; one of another supplier is reported as missing."""
    document = await db.scalar(
        select(SupplierDocument).where(SupplierDocument.id == document_id, SupplierDocument.supplier_id == supplier_id)
    )
    if document is None:
        raise _not_found()
    return document


@dataclass(frozen=True)
class DocumentUpload:
    document_type: SupplierDocumentType
    issue_date: date | None
    expiry_date: date | None
    filename: str | None
    data: bytes


async def upload_document(
    db: AsyncSession, storage: StorageBackend, actor: User, supplier_id: int, upload: DocumentUpload, today: date
) -> SupplierDocumentRead:
    await ensure_supplier_exists(db, supplier_id)
    document_type, issue_date, expiry_date, data = (
        upload.document_type,
        upload.issue_date,
        upload.expiry_date,
        upload.data,
    )
    if issue_date and expiry_date and expiry_date < issue_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="The expiry date cannot be before the issue date"
        )
    detected = detect_file_type(data, DOCUMENT_KINDS)
    if detected is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Upload a PDF, PNG or JPEG file."
        )
    count = await db.scalar(
        select(func.count()).select_from(SupplierDocument).where(SupplierDocument.supplier_id == supplier_id)
    )
    if (count or 0) >= MAX_DOCUMENTS_PER_SUPPLIER:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A supplier can have at most {MAX_DOCUMENTS_PER_SUPPLIER} documents",
        )

    content_type, extension = detected
    storage_key = new_storage_key("supplier-documents", extension)
    await storage.save(storage_key, data, content_type)
    document = SupplierDocument(
        supplier_id=supplier_id,
        document_type=document_type.value,
        issue_date=issue_date,
        expiry_date=expiry_date,
        filename=clean_filename(upload.filename),
        content_type=content_type,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        storage_key=storage_key,
        uploaded_by=actor.id,
    )
    db.add(document)
    await db.flush()
    await record_audit_event(
        db,
        user_id=actor.id,
        action="supplier_document_uploaded",
        entity_type="supplier",
        entity_id=supplier_id,
        extra_data={
            "document_id": document.id,
            "document_type": document.document_type,
            "expiry_date": expiry_date.isoformat() if expiry_date else None,
            "filename": document.filename,
        },
    )
    try:
        await db.commit()
    except Exception:
        await storage.delete(storage_key)
        raise
    await db.refresh(document)
    return to_read(document, actor, today)


async def read_document_file(
    db: AsyncSession, storage: StorageBackend, supplier_id: int, document_id: int
) -> tuple[SupplierDocument, bytes]:
    document = await get_document(db, supplier_id, document_id)
    try:
        return document, await storage.read(document.storage_key)
    except StoredObjectNotFoundError as exc:
        raise _not_found() from exc


async def delete_document(
    db: AsyncSession, storage: StorageBackend, actor: User, supplier_id: int, document_id: int
) -> None:
    document = await get_document(db, supplier_id, document_id)
    await record_audit_event(
        db,
        user_id=actor.id,
        action="supplier_document_removed",
        entity_type="supplier",
        entity_id=supplier_id,
        extra_data={"document_id": document.id, "document_type": document.document_type},
    )
    storage_key = document.storage_key
    await db.delete(document)
    await db.commit()
    # The record is gone either way; a file that cannot be deleted is an orphan, not a visible document.
    await storage.delete(storage_key)


def attention_conditions(statuses: frozenset[SupplierDocumentStatus], today: date) -> list[ColumnElement[bool]]:
    soon_until = today + timedelta(days=EXPIRING_SOON_DAYS)
    conditions: list[ColumnElement[bool]] = []
    if SupplierDocumentStatus.EXPIRED in statuses:
        conditions.append(SupplierDocument.expiry_date < today)
    if SupplierDocumentStatus.EXPIRING_SOON in statuses:
        conditions.append(SupplierDocument.expiry_date.between(today, soon_until))
    return conditions


async def documents_needing_attention(
    db: AsyncSession, today: date, statuses: frozenset[SupplierDocumentStatus]
) -> list[ExpiringDocumentRead]:
    """Documents across all active suppliers that are expiring soon and/or expired, soonest expiry first."""
    conditions = attention_conditions(statuses, today)
    if not conditions:
        return []
    rows = (
        await db.execute(
            select(SupplierDocument, User, Supplier)
            .join(User, User.id == SupplierDocument.uploaded_by)
            .join(Supplier, Supplier.id == SupplierDocument.supplier_id)
            .where(Supplier.is_active.is_(True), or_(*conditions))
            .order_by(SupplierDocument.expiry_date, SupplierDocument.id)
        )
    ).all()
    return [
        ExpiringDocumentRead(**to_read(document, uploader, today).model_dump(), supplier_name=owner.name)
        for document, uploader, owner in rows
    ]
