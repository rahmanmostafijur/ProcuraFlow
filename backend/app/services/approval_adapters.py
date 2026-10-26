"""Connects each kind of document to the approval engine: how to describe it, and what approving or rejecting does."""

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import AmendmentStatus, ApprovalDocumentType, InvoiceStatus, POStatus, PurchaseRequestStatus
from app.models.po_version import PurchaseOrderVersion
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_request import PurchaseRequest
from app.models.supplier_invoice import SupplierInvoice
from app.models.user import User
from app.services.approval_engine import ApprovalSubject, register_adapter
from app.services.audit_service import record_audit_event
from app.services.invoice_queries import INVOICE_LOAD
from app.services.invoice_transitions import mark_approved, send_back_to_draft
from app.services.po_pricing import lock_base_amounts, to_base_amount


def _conflict(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)


# --- purchase requests -------------------------------------------------------------------------------------------


def request_subject(request: PurchaseRequest, amount_base: Decimal | None = None) -> ApprovalSubject:
    return ApprovalSubject(
        document_type=ApprovalDocumentType.PURCHASE_REQUEST,
        document_id=request.id,
        owner_id=request.requester_id,
        owner_name=request.requester.full_name,
        noun="purchase request",
        label=request.request_number,
        title=request.title,
        submitted_at=request.submitted_at,
        cost_centre_id=request.cost_centre_id,
        document=request,
        amount_base=amount_base,
    )


class PurchaseRequestAdapter:
    document_type = ApprovalDocumentType.PURCHASE_REQUEST

    async def base_amount(self, db: AsyncSession, subject: ApprovalSubject) -> Decimal:
        request: PurchaseRequest = subject.document
        if request.base_estimated_total is not None:
            return request.base_estimated_total
        return await to_base_amount(db, request.estimated_total, request.currency_code)

    async def ensure_decidable(self, subject: ApprovalSubject) -> None:
        request: PurchaseRequest = subject.document
        if request.status != PurchaseRequestStatus.SUBMITTED:
            raise _conflict(f"Cannot decide a purchase request that is '{request.status.value}'")

    async def on_approved(self, db: AsyncSession, subject: ApprovalSubject, decider: User) -> None:
        request: PurchaseRequest = subject.document
        request.status = PurchaseRequestStatus.APPROVED
        request.decided_at = datetime.now(UTC)
        request.rejection_reason = None
        await record_audit_event(
            db,
            user_id=decider.id,
            action="purchase_request_approved",
            entity_type="purchase_request",
            entity_id=request.id,
        )

    async def on_rejected(self, db: AsyncSession, subject: ApprovalSubject, decider: User, comment: str) -> None:
        request: PurchaseRequest = subject.document
        request.status = PurchaseRequestStatus.REJECTED
        request.decided_at = datetime.now(UTC)
        request.rejection_reason = comment
        await record_audit_event(
            db,
            user_id=decider.id,
            action="purchase_request_rejected",
            entity_type="purchase_request",
            entity_id=request.id,
            extra_data={"reason": comment},
        )


# --- purchase orders ---------------------------------------------------------------------------------------------


def po_subject(po: PurchaseOrder, amount_base: Decimal | None = None) -> ApprovalSubject:
    return ApprovalSubject(
        document_type=ApprovalDocumentType.PURCHASE_ORDER,
        document_id=po.id,
        owner_id=po.created_by,
        owner_name=po.creator.full_name,
        noun="purchase order",
        label=po.po_number,
        title=f"{po.po_number} · {po.supplier.name}",
        submitted_at=None,
        cost_centre_id=po.cost_centre_id,
        document=po,
        amount_base=amount_base,
    )


class PurchaseOrderAdapter:
    document_type = ApprovalDocumentType.PURCHASE_ORDER

    async def base_amount(self, db: AsyncSession, subject: ApprovalSubject) -> Decimal:
        po: PurchaseOrder = subject.document
        if po.base_grand_total is not None:
            return po.base_grand_total
        return await to_base_amount(db, po.grand_total, po.currency_code)

    async def ensure_decidable(self, subject: ApprovalSubject) -> None:
        from app.services.purchase_order_service import ensure_transition_allowed  # noqa: PLC0415 - imported here to break an import cycle

        po: PurchaseOrder = subject.document
        ensure_transition_allowed(po.status, POStatus.APPROVED)

    async def on_approved(self, db: AsyncSession, subject: ApprovalSubject, decider: User) -> None:
        po: PurchaseOrder = subject.document
        # Before the state change: a missing exchange rate must leave the order submitted, not half-approved.
        await lock_base_amounts(db, po)
        po.status = POStatus.APPROVED
        po.approved_by = decider.id
        po.approved_at = datetime.now(UTC)
        await record_audit_event(
            db, user_id=decider.id, action="po_approved", entity_type="purchase_order", entity_id=po.id
        )

    async def on_rejected(self, db: AsyncSession, subject: ApprovalSubject, decider: User, comment: str) -> None:
        from app.services.purchase_order_service import cancel_purchase_order  # noqa: PLC0415 - imported here to break an import cycle

        po: PurchaseOrder = subject.document
        # The order lifecycle has no way back to draft, so a rejected order ends as cancelled with the reason kept.
        cancel_purchase_order(po)
        await record_audit_event(
            db,
            user_id=decider.id,
            action="po_rejected",
            entity_type="purchase_order",
            entity_id=po.id,
            extra_data={"reason": comment},
        )


# --- purchase order amendments -----------------------------------------------------------------------------------


def amendment_subject(
    version: PurchaseOrderVersion,
    po: PurchaseOrder,
    creator: User,
    amount_base: Decimal | None = None,
) -> ApprovalSubject:
    increase = Decimal(str(version.snapshot.get("budget_increase_base", "0")))
    return ApprovalSubject(
        document_type=ApprovalDocumentType.PURCHASE_ORDER_AMENDMENT,
        document_id=version.id,
        owner_id=version.created_by,
        owner_name=creator.full_name,
        noun="amendment",
        label=f"{po.po_number} v{version.version}",
        title=f"Amendment to {po.po_number}: {version.reason}",
        submitted_at=version.created_at,
        cost_centre_id=po.cost_centre_id,
        document=(version, po),
        amount_base=amount_base,
        budget_amount_base=increase,
    )


class PurchaseOrderAmendmentAdapter:
    document_type = ApprovalDocumentType.PURCHASE_ORDER_AMENDMENT

    async def base_amount(self, db: AsyncSession, subject: ApprovalSubject) -> Decimal:
        # Amendments always open their round when they are proposed, so this is only a safeguard: the new total at
        # the order's locked rate.
        version, po = subject.document
        rate = po.exchange_rate if po.exchange_rate is not None else Decimal(1)
        return Decimal(version.snapshot["grand_total"]) * rate

    async def ensure_decidable(self, subject: ApprovalSubject) -> None:
        version, _ = subject.document
        if version.status != AmendmentStatus.PENDING_APPROVAL:
            raise _conflict(f"Cannot decide an amendment that is '{version.status.value}'")

    async def on_approved(self, db: AsyncSession, subject: ApprovalSubject, decider: User) -> None:
        from app.services.po_amendment_service import apply_version  # noqa: PLC0415 - imported here to break an import cycle

        version, po = subject.document
        await apply_version(db, po, version, decider)

    async def on_rejected(self, db: AsyncSession, subject: ApprovalSubject, decider: User, comment: str) -> None:
        version, po = subject.document
        version.status = AmendmentStatus.REJECTED
        version.decided_at = datetime.now(UTC)
        await record_audit_event(
            db,
            user_id=decider.id,
            action="po_amendment_rejected",
            entity_type="purchase_order",
            entity_id=po.id,
            extra_data={"version": version.version, "reason": comment},
        )


# --- supplier invoice exceptions ---------------------------------------------------------------------------------


def invoice_subject(invoice: SupplierInvoice, amount_base: Decimal | None = None) -> ApprovalSubject:
    # No cost centre: approving an invoice never changes a budget, because budgets count orders.
    return ApprovalSubject(
        document_type=ApprovalDocumentType.INVOICE_EXCEPTION,
        document_id=invoice.id,
        owner_id=invoice.created_by,
        owner_name=invoice.creator.full_name,
        noun="invoice",
        label=f"{invoice.supplier.name} {invoice.invoice_number}",
        title=f"Invoice {invoice.invoice_number} from {invoice.supplier.name}",
        submitted_at=invoice.submitted_at,
        cost_centre_id=None,
        document=invoice,
        amount_base=amount_base,
    )


class InvoiceExceptionAdapter:
    document_type = ApprovalDocumentType.INVOICE_EXCEPTION

    async def base_amount(self, db: AsyncSession, subject: ApprovalSubject) -> Decimal:
        invoice: SupplierInvoice = subject.document
        return await to_base_amount(db, invoice.grand_total, invoice.currency_code)

    async def ensure_decidable(self, subject: ApprovalSubject) -> None:
        invoice: SupplierInvoice = subject.document
        if invoice.status != InvoiceStatus.EXCEPTION:
            raise _conflict(f"Cannot decide an invoice that is '{invoice.status.value}'")

    async def on_approved(self, db: AsyncSession, subject: ApprovalSubject, decider: User) -> None:
        await mark_approved(db, subject.document, decider)

    async def on_rejected(self, db: AsyncSession, subject: ApprovalSubject, decider: User, comment: str) -> None:
        await send_back_to_draft(db, subject.document, decider, comment)


register_adapter(PurchaseRequestAdapter())
register_adapter(PurchaseOrderAdapter())
register_adapter(PurchaseOrderAmendmentAdapter())
register_adapter(InvoiceExceptionAdapter())


# --- loading a document by id (for the approvals queue and for who-can-see checks) -------------------------------


async def subject_by_id(
    db: AsyncSession, document_type: ApprovalDocumentType, document_id: int
) -> ApprovalSubject | None:
    """The document described for the engine, or ``None`` if it no longer exists. Does not lock anything."""
    if document_type == ApprovalDocumentType.PURCHASE_REQUEST:
        request = await db.scalar(
            select(PurchaseRequest)
            .options(selectinload(PurchaseRequest.requester))
            .where(PurchaseRequest.id == document_id)
        )
        return None if request is None else request_subject(request)
    if document_type == ApprovalDocumentType.PURCHASE_ORDER:
        from app.services.purchase_order_service import PO_LOAD_OPTIONS  # noqa: PLC0415 - imported here to break an import cycle

        po = await db.scalar(select(PurchaseOrder).options(*PO_LOAD_OPTIONS).where(PurchaseOrder.id == document_id))
        return None if po is None else po_subject(po)
    if document_type == ApprovalDocumentType.PURCHASE_ORDER_AMENDMENT:
        from app.services.purchase_order_service import PO_LOAD_OPTIONS  # noqa: PLC0415 - imported here to break an import cycle

        version = await db.get(PurchaseOrderVersion, document_id)
        if version is None:
            return None
        po = await db.scalar(select(PurchaseOrder).options(*PO_LOAD_OPTIONS).where(PurchaseOrder.id == version.po_id))
        creator = await db.get(User, version.created_by)
        return None if po is None or creator is None else amendment_subject(version, po, creator)
    invoice = await db.scalar(select(SupplierInvoice).options(*INVOICE_LOAD).where(SupplierInvoice.id == document_id))
    return None if invoice is None else invoice_subject(invoice)
