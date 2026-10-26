from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.deps import CurrentUser, DbSession, require_permission
from app.models.enums import InvoiceStatus
from app.models.payment import Payment
from app.models.supplier_invoice import SupplierInvoice
from app.models.user import User
from app.schemas.payment import PaymentCreate, PaymentRead
from app.schemas.supplier_invoice import (
    InvoiceCreate,
    InvoiceDecision,
    InvoiceListResponse,
    InvoiceRead,
    InvoiceReasonBody,
    InvoiceRejection,
    InvoiceUpdate,
)
from app.services import invoice_service, invoice_workflow_service, payment_service
from app.services.invoice_queries import InvoiceFilter

router = APIRouter(prefix="/supplier-invoices", tags=["supplier-invoices"])

RequireInvoiceRead = Annotated[User, Depends(require_permission("invoice:read"))]
RequireInvoiceWrite = Annotated[User, Depends(require_permission("invoice:write"))]
RequireInvoiceApprove = Annotated[User, Depends(require_permission("invoice:approve"))]
RequirePaymentWrite = Annotated[User, Depends(require_permission("payment:write"))]


@router.get("", response_model=InvoiceListResponse)
async def list_invoices(
    db: DbSession,
    _: RequireInvoiceRead,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Annotated[InvoiceStatus | None, Query(alias="status")] = None,
    supplier_id: int | None = None,
    po_id: int | None = None,
    due_before: date | None = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
) -> InvoiceListResponse:
    """Invoices with totals (counts by status, payables) for everything the filters match."""
    flt = InvoiceFilter(
        status=status_filter, supplier_id=supplier_id, po_id=po_id, due_before=due_before, search=search
    )
    return await invoice_service.list_invoices(db, flt, page, page_size)


@router.post("", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
async def create_invoice(payload: InvoiceCreate, db: DbSession, user: RequireInvoiceWrite) -> SupplierInvoice:
    """Record a supplier invoice against an ordered or received purchase order, as a draft."""
    return await invoice_service.create_invoice(db, payload, user)


@router.get("/{invoice_id}", response_model=InvoiceRead)
async def get_invoice(invoice_id: int, db: DbSession, user: RequireInvoiceRead) -> SupplierInvoice:
    return await invoice_service.read_invoice(db, invoice_id, user)


@router.patch("/{invoice_id}", response_model=InvoiceRead)
async def update_invoice(
    invoice_id: int, payload: InvoiceUpdate, db: DbSession, user: RequireInvoiceWrite
) -> SupplierInvoice:
    return await invoice_service.update_invoice(db, invoice_id, payload, user)


@router.post("/{invoice_id}/submit", response_model=InvoiceRead)
async def submit_invoice(invoice_id: int, db: DbSession, user: RequireInvoiceWrite) -> SupplierInvoice:
    """Match the invoice against its order: it becomes matched, or an exception with its reasons."""
    return await invoice_workflow_service.submit_invoice(db, invoice_id, user)


@router.post("/{invoice_id}/approve", response_model=InvoiceRead)
async def approve_invoice(
    invoice_id: int, db: DbSession, user: CurrentUser, payload: InvoiceDecision | None = None
) -> SupplierInvoice:
    """Approve a matched invoice, or decide the current approval step of an exception."""
    return await invoice_workflow_service.approve_invoice(db, invoice_id, user, payload.comment if payload else None)


@router.post("/{invoice_id}/reject", response_model=InvoiceRead)
async def reject_invoice(
    invoice_id: int, payload: InvoiceRejection, db: DbSession, user: CurrentUser
) -> SupplierInvoice:
    """Send the invoice back to draft with a reason."""
    return await invoice_workflow_service.reject_invoice(db, invoice_id, user, payload.comment)


@router.post("/{invoice_id}/hold", response_model=InvoiceRead)
async def hold_invoice(
    invoice_id: int, payload: InvoiceReasonBody, db: DbSession, user: RequireInvoiceApprove
) -> SupplierInvoice:
    return await invoice_workflow_service.hold_invoice(db, invoice_id, user, payload.reason)


@router.post("/{invoice_id}/release", response_model=InvoiceRead)
async def release_invoice(invoice_id: int, db: DbSession, user: RequireInvoiceApprove) -> SupplierInvoice:
    """Take the invoice off hold: it returns to the state it was in."""
    return await invoice_workflow_service.release_invoice(db, invoice_id, user)


@router.post("/{invoice_id}/void", response_model=InvoiceRead)
async def void_invoice(
    invoice_id: int, payload: InvoiceReasonBody, db: DbSession, user: RequireInvoiceWrite
) -> SupplierInvoice:
    return await invoice_workflow_service.void_invoice(db, invoice_id, user, payload.reason)


@router.get("/{invoice_id}/payments", response_model=list[PaymentRead])
async def list_payments(invoice_id: int, db: DbSession, _: RequireInvoiceRead) -> list[Payment]:
    return await payment_service.list_payments(db, invoice_id)


@router.post("/{invoice_id}/payments", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
async def record_payment(invoice_id: int, payload: PaymentCreate, db: DbSession, user: RequirePaymentWrite) -> Payment:
    """Record a manual payment against an approved invoice, never more than what is still open."""
    return await payment_service.record_payment(db, invoice_id, payload, user)
