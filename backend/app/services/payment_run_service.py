"""Payment runs: approved invoices grouped into one batch that a second person releases.

Creating a run changes nothing about the invoices. Releasing re-checks every invoice under a row lock, in one
transaction, and records one payment per item, so a run can never pay more than an invoice's open amount.

``get_run`` returns a run with its items and is the seam a later export of a released run (bank file) builds on.
"""

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from app.core.clock import today_in
from app.models.enums import InvoiceStatus, PaymentRunStatus
from app.models.payment import PAYMENT_RUN_NUMBER_SEQUENCE, PaymentRun, PaymentRunItem
from app.models.supplier_invoice import SupplierInvoice
from app.models.user import User
from app.schemas.payment import PaymentRunCreate, PaymentRunItemRead, PaymentRunRead
from app.schemas.person import PersonRead
from app.services.audit_service import record_audit_event
from app.services.company_settings_service import get_company_settings
from app.services.payment_service import apply_payment

RUN_LOAD = (
    selectinload(PaymentRun.items).selectinload(PaymentRunItem.invoice).selectinload(SupplierInvoice.supplier),
    selectinload(PaymentRun.creator),
    selectinload(PaymentRun.releaser),
)


def _error(code: int, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail=message)


def _person(user: User | None) -> PersonRead | None:
    return None if user is None else PersonRead(id=user.id, full_name=user.full_name)


def to_read(run: PaymentRun) -> PaymentRunRead:
    creator = _person(run.creator)
    assert creator is not None  # noqa: S101 - a run always has a creator
    return PaymentRunRead(
        id=run.id,
        number=run.number,
        status=run.status,
        method=run.method,
        currency_code=run.currency_code,
        total=run.total,
        created_by=run.created_by,
        creator=creator,
        released_by=run.released_by,
        releaser=_person(run.releaser),
        released_at=run.released_at,
        created_at=run.created_at,
        items=[
            PaymentRunItemRead(
                id=item.id,
                invoice_id=item.invoice_id,
                invoice_number=item.invoice.invoice_number,
                supplier_id=item.invoice.supplier_id,
                supplier_name=item.invoice.supplier.name,
                amount=item.amount,
            )
            for item in run.items
        ],
    )


async def get_run(db: AsyncSession, run_id: int, *, for_update: bool = False) -> PaymentRun:
    stmt = select(PaymentRun).options(*RUN_LOAD).where(PaymentRun.id == run_id)
    if for_update:
        stmt = stmt.with_for_update(of=PaymentRun)
    run = await db.scalar(stmt.execution_options(populate_existing=True))
    if run is None:
        raise _error(status.HTTP_404_NOT_FOUND, "Payment run not found")
    return run


def list_statement(status_filter: PaymentRunStatus | None) -> Select[tuple[PaymentRun]]:
    stmt = select(PaymentRun).options(*RUN_LOAD).order_by(PaymentRun.id.desc())
    if status_filter is not None:
        stmt = stmt.where(PaymentRun.status == status_filter)
    return stmt


async def _lock_invoices(db: AsyncSession, invoice_ids: list[int]) -> list[SupplierInvoice]:
    """The invoices, locked in ascending id order so two runs or payments cannot deadlock."""
    rows = await db.execute(
        select(SupplierInvoice)
        .where(SupplierInvoice.id.in_(invoice_ids))
        .order_by(SupplierInvoice.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return list(rows.scalars().all())


async def _invoice_ids_in_open_runs(db: AsyncSession, invoice_ids: list[int]) -> list[int]:
    rows = await db.execute(
        select(PaymentRunItem.invoice_id)
        .join(PaymentRun, PaymentRun.id == PaymentRunItem.run_id)
        .where(PaymentRunItem.invoice_id.in_(invoice_ids), PaymentRun.status == PaymentRunStatus.DRAFT)
    )
    return sorted(set(rows.scalars().all()))


def _ensure_creatable(invoices: list[SupplierInvoice], requested: list[int]) -> None:
    missing = sorted(set(requested) - {invoice.id for invoice in invoices})
    if missing:
        raise _error(status.HTTP_400_BAD_REQUEST, f"Unknown invoice ids: {missing}")
    not_approved = [invoice for invoice in invoices if invoice.status != InvoiceStatus.APPROVED]
    if not_approved:
        listed = ", ".join(f"{invoice.invoice_number} ({invoice.status.value})" for invoice in not_approved)
        raise _error(status.HTTP_409_CONFLICT, f"Only approved invoices can go into a payment run: {listed}")
    currencies = sorted({invoice.currency_code for invoice in invoices})
    if len(currencies) > 1:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"A payment run pays one currency; these invoices are in {', '.join(currencies)}",
        )


async def create_run(db: AsyncSession, payload: PaymentRunCreate, actor: User) -> PaymentRun:
    requested = sorted(set(payload.invoice_ids))
    invoices = await _lock_invoices(db, requested)
    _ensure_creatable(invoices, requested)
    already = await _invoice_ids_in_open_runs(db, requested)
    if already:
        raise _error(status.HTTP_409_CONFLICT, f"Invoices {already} are already in an open payment run")

    number = await db.scalar(PAYMENT_RUN_NUMBER_SEQUENCE.next_value())
    run = PaymentRun(
        number=f"PAY-{today_in((await get_company_settings(db)).timezone).year}-{number:05d}",
        status=PaymentRunStatus.DRAFT,
        method=payload.method,
        currency_code=invoices[0].currency_code,
        created_by=actor.id,
    )
    run.items = [PaymentRunItem(invoice_id=invoice.id, amount=invoice.open_amount) for invoice in invoices]
    run.total = sum((item.amount for item in run.items), Decimal(0))
    db.add(run)
    await db.flush()
    await record_audit_event(
        db,
        user_id=actor.id,
        action="payment_run_created",
        entity_type="payment_run",
        entity_id=run.id,
        extra_data={"number": run.number, "invoice_ids": requested, "total": str(run.total)},
    )
    await db.commit()
    return await get_run(db, run.id)


async def release_run(db: AsyncSession, run_id: int, actor: User) -> PaymentRun:
    run = await get_run(db, run_id, for_update=True)
    if run.status != PaymentRunStatus.DRAFT:
        raise _error(status.HTTP_409_CONFLICT, f"Cannot release a payment run that is '{run.status.value}'")
    if run.created_by == actor.id:
        raise _error(
            status.HTTP_403_FORBIDDEN,
            "You created this payment run, so a second person must release it.",
        )
    invoices = {invoice.id: invoice for invoice in await _lock_invoices(db, [item.invoice_id for item in run.items])}
    today = today_in((await get_company_settings(db)).timezone)
    for item in run.items:
        invoice = invoices[item.invoice_id]
        if invoice.status != InvoiceStatus.APPROVED or invoice.open_amount != item.amount:
            raise _error(
                status.HTTP_409_CONFLICT,
                f"Invoice {invoice.invoice_number} changed after the run was created (it is "
                f"'{invoice.status.value}' with {invoice.open_amount} open); cancel this run and create a new one.",
            )
    for item in run.items:
        await apply_payment(
            db,
            invoices[item.invoice_id],
            amount=item.amount,
            method=run.method,
            paid_on=today,
            reference=run.number,
            actor=actor,
            payment_run_id=run.id,
        )
    run.status = PaymentRunStatus.RELEASED
    run.released_by = actor.id
    run.released_at = datetime.now(UTC)
    await record_audit_event(
        db,
        user_id=actor.id,
        action="payment_run_released",
        entity_type="payment_run",
        entity_id=run.id,
        extra_data={"number": run.number, "total": str(run.total), "invoices": len(run.items)},
    )
    await db.commit()
    return await get_run(db, run_id)


async def cancel_run(db: AsyncSession, run_id: int, actor: User) -> PaymentRun:
    run = await get_run(db, run_id, for_update=True)
    if run.status != PaymentRunStatus.DRAFT:
        raise _error(status.HTTP_409_CONFLICT, f"Cannot cancel a payment run that is '{run.status.value}'")
    run.status = PaymentRunStatus.CANCELLED
    await record_audit_event(
        db,
        user_id=actor.id,
        action="payment_run_cancelled",
        entity_type="payment_run",
        entity_id=run.id,
        extra_data={"number": run.number},
    )
    await db.commit()
    return await get_run(db, run_id)
