"""The state changes an invoice decision causes. Shared by the direct approval of a matched invoice and the approval
engine, which applies them when an exception is approved or rejected, so both paths end in the same state."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import InvoiceStatus
from app.models.supplier_invoice import SupplierInvoice
from app.models.user import User
from app.services.audit_service import record_audit_event
from app.services.invoice_pricing import lock_invoice_base_amounts


async def mark_approved(db: AsyncSession, invoice: SupplierInvoice, decider: User) -> None:
    # Before the state change: a missing exchange rate must leave the invoice as it was, not half-approved.
    await lock_invoice_base_amounts(db, invoice)
    invoice.status = InvoiceStatus.APPROVED
    invoice.approved_by = decider.id
    invoice.approved_at = datetime.now(UTC)
    invoice.rejection_reason = None
    await record_audit_event(
        db,
        user_id=decider.id,
        action="invoice_approved",
        entity_type="supplier_invoice",
        entity_id=invoice.id,
        extra_data={"invoice_number": invoice.invoice_number, "base_grand_total": str(invoice.base_grand_total)},
    )


async def send_back_to_draft(db: AsyncSession, invoice: SupplierInvoice, decider: User, reason: str) -> None:
    """A rejected invoice returns to draft with the reason kept, so it can be corrected and submitted again."""
    invoice.status = InvoiceStatus.DRAFT
    invoice.rejection_reason = reason
    await record_audit_event(
        db,
        user_id=decider.id,
        action="invoice_rejected",
        entity_type="supplier_invoice",
        entity_id=invoice.id,
        extra_data={"invoice_number": invoice.invoice_number, "reason": reason},
    )
