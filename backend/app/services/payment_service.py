"""Recording payments against approved invoices. Manual only: nothing here moves money."""

from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.clock import today_in
from app.core.money import quantize_money
from app.models.currency import Currency
from app.models.enums import InvoiceStatus, PaymentMethod
from app.models.payment import Payment
from app.models.supplier_invoice import SupplierInvoice
from app.models.user import User
from app.schemas.common import format_money
from app.schemas.payment import PaymentCreate
from app.services.audit_service import record_audit_event
from app.services.company_settings_service import get_company_settings
from app.services.invoice_queries import get_invoice


def _error(code: int, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail=message)


def ensure_payable(invoice: SupplierInvoice) -> None:
    """Only an approved invoice can be paid: not one on hold, void, already paid or still being matched."""
    if invoice.status != InvoiceStatus.APPROVED:
        raise _error(
            status.HTTP_409_CONFLICT, f"Only approved invoices can be paid; this one is '{invoice.status.value}'"
        )


async def apply_payment(
    db: AsyncSession,
    invoice: SupplierInvoice,
    *,
    amount: Decimal,
    method: PaymentMethod,
    paid_on: date,
    reference: str | None,
    actor: User,
    payment_run_id: int | None = None,
) -> Payment:
    """Add the payment and update what is paid. The caller holds the invoice's row lock, so the open amount it
    checked cannot change under it, and commits."""
    ensure_payable(invoice)
    currency = await db.get(Currency, invoice.currency_code)
    assert currency is not None  # noqa: S101 - the invoice references it by foreign key
    if amount != quantize_money(amount, currency.minor_units):
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"{invoice.currency_code} amounts have at most {currency.minor_units} decimal places",
        )
    if amount > invoice.open_amount:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"The payment of {format_money(amount)} {invoice.currency_code} is more than the open amount of "
            f"{format_money(invoice.open_amount)} {invoice.currency_code}",
        )
    payment = Payment(
        invoice_id=invoice.id,
        payment_run_id=payment_run_id,
        amount=amount,
        currency_code=invoice.currency_code,
        method=method,
        paid_on=paid_on,
        reference=reference,
        created_by=actor.id,
    )
    db.add(payment)
    invoice.paid_total += amount
    fully_paid = invoice.paid_total >= invoice.grand_total
    if fully_paid:
        invoice.status = InvoiceStatus.PAID
    await db.flush()
    await record_audit_event(
        db,
        user_id=actor.id,
        action="payment_recorded",
        entity_type="supplier_invoice",
        entity_id=invoice.id,
        extra_data={
            "payment_id": payment.id,
            "amount": str(amount),
            "currency": invoice.currency_code,
            "method": method.value,
            "payment_run_id": payment_run_id,
            "fully_paid": fully_paid,
        },
    )
    return payment


async def record_payment(db: AsyncSession, invoice_id: int, payload: PaymentCreate, actor: User) -> Payment:
    invoice = await get_invoice(db, invoice_id, for_update=True)
    today = today_in((await get_company_settings(db)).timezone)
    if payload.paid_on is not None and payload.paid_on > today:
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "The payment date cannot be in the future")
    payment = await apply_payment(
        db,
        invoice,
        amount=payload.amount,
        method=payload.method,
        paid_on=payload.paid_on or today,
        reference=payload.reference,
        actor=actor,
    )
    await db.commit()
    return await get_payment(db, payment.id)


async def get_payment(db: AsyncSession, payment_id: int) -> Payment:
    payment = await db.scalar(
        select(Payment)
        .options(selectinload(Payment.creator))
        .where(Payment.id == payment_id)
        .execution_options(populate_existing=True)
    )
    assert payment is not None  # noqa: S101 - read back right after it was written
    return payment


async def list_payments(db: AsyncSession, invoice_id: int) -> list[Payment]:
    await get_invoice(db, invoice_id)
    stmt = (
        select(Payment)
        .options(selectinload(Payment.creator))
        .where(Payment.invoice_id == invoice_id)
        .order_by(Payment.id)
    )
    return list((await db.execute(stmt)).scalars().all())
