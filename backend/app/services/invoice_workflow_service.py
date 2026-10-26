"""The life of an invoice after it is recorded: submit and match, approve or reject, hold, release and void.

    draft -> matched | exception          (submit; the match decides which)
    matched -> approved                   (someone with invoice:approve other than the person who recorded it)
    exception -> approved | draft         (the approval engine: rules, limits, delegation; rejection sends it back)
    approved | matched | exception -> on_hold -> where it was (release)
    draft | matched | exception | on_hold | approved (nothing paid) -> void
    approved -> paid                      (payments cover the total; see payment_service)

Every illegal move is refused with a 409. Every function locks the invoice row first, so two people cannot move the
same invoice at once.
"""

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import ApprovalDocumentType, InvoiceStatus
from app.models.purchase_order import PurchaseOrder
from app.models.supplier_invoice import SupplierInvoice
from app.models.user import User
from app.services import approval_adapters, approval_engine, invoice_access, invoice_matching_service
from app.services.audit_service import record_audit_event
from app.services.company_settings_service import get_company_settings
from app.services.invoice_queries import get_invoice
from app.services.invoice_service import ensure_po_is_invoiceable
from app.services.invoice_transitions import mark_approved, send_back_to_draft
from app.services.po_pricing import to_base_amount

HOLDABLE = (InvoiceStatus.APPROVED, InvoiceStatus.MATCHED, InvoiceStatus.EXCEPTION)
VOIDABLE = (
    InvoiceStatus.DRAFT,
    InvoiceStatus.MATCHED,
    InvoiceStatus.EXCEPTION,
    InvoiceStatus.ON_HOLD,
    InvoiceStatus.APPROVED,
)


def _conflict(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)


def _ensure_status(invoice: SupplierInvoice, allowed: tuple[InvoiceStatus, ...], action: str) -> None:
    if invoice.status not in allowed:
        raise _conflict(f"Cannot {action} an invoice that is '{invoice.status.value}'")


async def _lock_visible(db: AsyncSession, invoice_id: int, actor: User) -> tuple[SupplierInvoice, User]:
    invoice, actor = await invoice_access.load_for(db, invoice_id, actor, for_update=True)
    if not await invoice_access.can_view(db, invoice, actor):
        raise invoice_access.not_found()
    return invoice, actor


async def _lock_purchase_order(db: AsyncSession, po_id: int) -> PurchaseOrder:
    """Lock the order so two invoices for it cannot be matched against the same remaining quantity."""
    po = await db.scalar(
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.items))
        .where(PurchaseOrder.id == po_id)
        .with_for_update(of=PurchaseOrder)
        .execution_options(populate_existing=True)
    )
    assert po is not None  # noqa: S101 - the invoice references it by foreign key
    return po


async def submit_invoice(db: AsyncSession, invoice_id: int, actor: User) -> SupplierInvoice:
    """Match the invoice; a clean match is ready for approval, anything else becomes an exception with reasons."""
    invoice, actor = await invoice_access.load_for(db, invoice_id, actor, for_update=True)
    invoice_access.ensure_can_modify(invoice, actor)
    _ensure_status(invoice, (InvoiceStatus.DRAFT,), "submit")
    po = await _lock_purchase_order(db, invoice.po_id)
    ensure_po_is_invoiceable(po)

    settings = await get_company_settings(db)
    result = await invoice_matching_service.match_invoice(
        db, invoice, po, settings.invoice_matching, settings.invoice_tolerance_percent
    )
    invoice.match_mode = result.mode
    invoice.tolerance_percent = result.tolerance_percent
    invoice.exception_reasons = result.reasons
    invoice.submitted_at = datetime.now(UTC)
    invoice.rejection_reason = None
    if result.is_match:
        invoice.status = InvoiceStatus.MATCHED
    else:
        invoice.status = InvoiceStatus.EXCEPTION
        amount_base = await to_base_amount(db, invoice.grand_total, invoice.currency_code)
        await approval_engine.open_round(db, approval_adapters.invoice_subject(invoice, amount_base))
    await record_audit_event(
        db,
        user_id=actor.id,
        action="invoice_submitted",
        entity_type="supplier_invoice",
        entity_id=invoice.id,
        extra_data={
            "invoice_number": invoice.invoice_number,
            "result": invoice.status.value,
            "mode": result.mode.value,
            "reasons": [reason["code"] for reason in result.reasons],
        },
    )
    await db.commit()
    return await get_invoice(db, invoice_id)


async def approve_invoice(
    db: AsyncSession, invoice_id: int, actor: User, comment: str | None = None
) -> SupplierInvoice:
    """Approve a matched invoice directly, or decide the current approval step of an exception."""
    invoice, actor = await _lock_visible(db, invoice_id, actor)
    if invoice.status == InvoiceStatus.MATCHED:
        invoice_access.require_approve_permission(actor)
        if invoice.created_by == actor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="You cannot approve an invoice you created."
            )
        await mark_approved(db, invoice, actor)
    else:
        await approval_engine.decide(
            db, approval_adapters.invoice_subject(invoice), actor, approve=True, comment=comment
        )
    await db.commit()
    return await get_invoice(db, invoice_id)


async def reject_invoice(db: AsyncSession, invoice_id: int, actor: User, comment: str) -> SupplierInvoice:
    """Send the invoice back to draft with the reason; for an exception this is a rejection at the current step."""
    invoice, actor = await _lock_visible(db, invoice_id, actor)
    if invoice.status == InvoiceStatus.MATCHED:
        invoice_access.require_approve_permission(actor)
        if invoice.created_by == actor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="You cannot reject an invoice you created."
            )
        await send_back_to_draft(db, invoice, actor, comment)
    else:
        await approval_engine.decide(
            db, approval_adapters.invoice_subject(invoice), actor, approve=False, comment=comment
        )
    await db.commit()
    return await get_invoice(db, invoice_id)


async def hold_invoice(db: AsyncSession, invoice_id: int, actor: User, reason: str) -> SupplierInvoice:
    invoice, actor = await invoice_access.load_for(db, invoice_id, actor, for_update=True)
    invoice_access.require_approve_permission(actor)
    _ensure_status(invoice, HOLDABLE, "put on hold")
    invoice.status_before_hold = invoice.status
    invoice.status = InvoiceStatus.ON_HOLD
    invoice.hold_reason = reason
    await record_audit_event(
        db,
        user_id=actor.id,
        action="invoice_held",
        entity_type="supplier_invoice",
        entity_id=invoice.id,
        extra_data={"invoice_number": invoice.invoice_number, "reason": reason},
    )
    await db.commit()
    return await get_invoice(db, invoice_id)


async def release_invoice(db: AsyncSession, invoice_id: int, actor: User) -> SupplierInvoice:
    invoice, actor = await invoice_access.load_for(db, invoice_id, actor, for_update=True)
    invoice_access.require_approve_permission(actor)
    _ensure_status(invoice, (InvoiceStatus.ON_HOLD,), "release")
    restored = invoice.status_before_hold or InvoiceStatus.MATCHED
    invoice.status = restored
    invoice.status_before_hold = None
    invoice.hold_reason = None
    await record_audit_event(
        db,
        user_id=actor.id,
        action="invoice_released",
        entity_type="supplier_invoice",
        entity_id=invoice.id,
        extra_data={"invoice_number": invoice.invoice_number, "status": restored.value},
    )
    await db.commit()
    return await get_invoice(db, invoice_id)


async def void_invoice(db: AsyncSession, invoice_id: int, actor: User, reason: str) -> SupplierInvoice:
    """Cancel an invoice recorded in error. It stops counting for matching, duplicates and payables."""
    invoice, actor = await invoice_access.load_for(db, invoice_id, actor, for_update=True)
    invoice_access.ensure_can_modify(invoice, actor)
    _ensure_status(invoice, VOIDABLE, "void")
    if invoice.paid_total > 0:
        raise _conflict("An invoice with payments cannot be voided")
    await approval_engine.skip_open_steps(db, ApprovalDocumentType.INVOICE_EXCEPTION, invoice.id)
    invoice.status = InvoiceStatus.VOID
    invoice.void_reason = reason
    invoice.status_before_hold = None
    await record_audit_event(
        db,
        user_id=actor.id,
        action="invoice_voided",
        entity_type="supplier_invoice",
        entity_id=invoice.id,
        extra_data={"invoice_number": invoice.invoice_number, "reason": reason},
    )
    await db.commit()
    return await get_invoice(db, invoice_id)
