"""The supplier portal. Every route here is for supplier accounts only and is scoped by ``PortalScope``, which takes
the supplier from the signed-in account: no route accepts a supplier id."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status

from app.core.uploads import download_response, read_upload
from app.models.enums import InvoiceStatus, POStatus, SupplierDocumentType
from app.schemas.attachment import AttachmentRead
from app.schemas.common import PaginatedResponse
from app.schemas.portal import (
    PortalInvoiceCreate,
    PortalInvoiceRead,
    PortalMe,
    PortalOrderRead,
    PortalOrderSummary,
)
from app.schemas.supplier_document import SupplierDocumentRead
from app.services import attachment_service, supplier_document_service
from app.services.portal_scope import Portal
from app.services.supplier_document_service import DocumentUpload
from app.services.today import Today
from app.storage import StorageBackend, get_storage

router = APIRouter(prefix="/portal", tags=["portal"])

Storage = Annotated[StorageBackend, Depends(get_storage)]
PageNumber = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


@router.get("/me", response_model=PortalMe)
async def me(portal: Portal) -> PortalMe:
    return portal.me()


@router.get("/orders", response_model=PaginatedResponse[PortalOrderSummary])
async def list_orders(
    portal: Portal, status: POStatus | None = None, page: PageNumber = 1, page_size: PageSize = 20
) -> PaginatedResponse[PortalOrderSummary]:
    """The supplier's orders from the moment they are placed with it; drafts and unapproved orders never appear."""
    return await portal.list_orders(status, page, page_size)


@router.get("/orders/{po_id}", response_model=PortalOrderRead)
async def get_order(po_id: int, portal: Portal) -> PortalOrderRead:
    return await portal.get_order(po_id)


@router.post("/orders/{po_id}/acknowledge", response_model=PortalOrderRead)
async def acknowledge_order(po_id: int, portal: Portal) -> PortalOrderRead:
    """Confirm the order. Safe to repeat: the first acknowledgement keeps its time and person."""
    return await portal.acknowledge_order(po_id)


@router.get("/invoices", response_model=PaginatedResponse[PortalInvoiceRead])
async def list_invoices(
    portal: Portal, status: InvoiceStatus | None = None, page: PageNumber = 1, page_size: PageSize = 20
) -> PaginatedResponse[PortalInvoiceRead]:
    return await portal.list_invoices(status, page, page_size)


@router.post("/invoices", response_model=PortalInvoiceRead, status_code=status.HTTP_201_CREATED)
async def create_invoice(payload: PortalInvoiceCreate, portal: Portal) -> PortalInvoiceRead:
    """Send an invoice for one of the supplier's orders. It arrives as a draft for finance to review."""
    return await portal.create_invoice(payload)


@router.get("/invoices/{invoice_id}", response_model=PortalInvoiceRead)
async def get_invoice(invoice_id: int, portal: Portal) -> PortalInvoiceRead:
    return await portal.get_invoice(invoice_id)


@router.get("/invoices/{invoice_id}/files", response_model=list[AttachmentRead])
async def list_invoice_files(invoice_id: int, portal: Portal) -> list[AttachmentRead]:
    return await portal.list_invoice_files(invoice_id)


@router.post("/invoices/{invoice_id}/files", response_model=AttachmentRead, status_code=status.HTTP_201_CREATED)
async def upload_invoice_file(
    invoice_id: int, portal: Portal, storage: Storage, file: Annotated[UploadFile, File()]
) -> AttachmentRead:
    """Attach the invoice PDF or a photo of it (PDF, PNG or JPEG) to a draft invoice."""
    data = await read_upload(file, attachment_service.MAX_ATTACHMENT_BYTES)
    return await portal.attach_to_invoice(storage, invoice_id, file.filename, data)


@router.get("/invoices/{invoice_id}/files/{attachment_id}/download")
async def download_invoice_file(invoice_id: int, attachment_id: int, portal: Portal, storage: Storage) -> Response:
    attachment, data = await portal.read_invoice_file(storage, invoice_id, attachment_id)
    return download_response(data, attachment.content_type, attachment.filename)


@router.get("/documents", response_model=list[SupplierDocumentRead])
async def list_documents(portal: Portal, today: Today) -> list[SupplierDocumentRead]:
    return await portal.list_documents(today)


@router.post("/documents", response_model=SupplierDocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    portal: Portal,
    storage: Storage,
    today: Today,
    document_type: Annotated[SupplierDocumentType, Form()],
    file: Annotated[UploadFile, File()],
    issue_date: Annotated[date | None, Form()] = None,
    expiry_date: Annotated[date | None, Form()] = None,
) -> SupplierDocumentRead:
    data = await read_upload(file, supplier_document_service.MAX_DOCUMENT_BYTES)
    upload = DocumentUpload(document_type, issue_date, expiry_date, file.filename, data)
    return await portal.upload_document(storage, upload, today)


@router.get("/documents/{document_id}/download")
async def download_document(document_id: int, portal: Portal, storage: Storage) -> Response:
    document, data = await portal.read_document(storage, document_id)
    return download_response(data, document.content_type, document.filename)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: int, portal: Portal, storage: Storage) -> Response:
    await portal.delete_document(storage, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
