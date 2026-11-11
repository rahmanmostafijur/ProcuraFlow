"""Seed step 7: put the year on the calendar.

The API stamps every document with the moment it is created, so after the seed has built the year the timeline step
moves the *timestamps* of those documents (and nothing else: no amount, status, quantity or link) to the dates the
plan gave them. Invoice and payment dates were already sent through the API; delivery dates are recomputed here from
the delivery date the order carries, the way the receipt would have decided them on the day.
"""

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import DateTime, case, cast, func, literal, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.demo.procure import OrderRecord
from app.models.approval import ApprovalStep
from app.models.delivery import Delivery
from app.models.enums import ApprovalDocumentType, DeliveryStatus
from app.models.goods_receipt import GoodsReceipt
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_request import PurchaseRequest
from app.models.supplier_invoice import SupplierInvoice

REQUEST_LEAD_DAYS = 3
INVOICE_APPROVAL_DAYS = 3
MORNING, NOON, AFTERNOON = time(9), time(12), time(15)


def at(day: date, when: time) -> datetime:
    return datetime.combine(day, when, tzinfo=UTC)


async def _date_order(db: AsyncSession, record: OrderRecord) -> None:
    ordered, decided = at(record.order_date, MORNING), at(record.order_date, NOON)
    await db.execute(update(PurchaseOrder).where(PurchaseOrder.id == record.po_id).values(created_at=ordered))
    await db.execute(
        update(PurchaseOrder)
        .where(PurchaseOrder.id == record.po_id, PurchaseOrder.approved_at.is_not(None))
        .values(approved_at=decided)
    )
    await db.execute(
        update(ApprovalStep)
        .where(
            ApprovalStep.document_type == ApprovalDocumentType.PURCHASE_ORDER,
            ApprovalStep.document_id == record.po_id,
        )
        .values(created_at=ordered)
    )
    await db.execute(
        update(ApprovalStep)
        .where(
            ApprovalStep.document_type == ApprovalDocumentType.PURCHASE_ORDER,
            ApprovalStep.document_id == record.po_id,
            ApprovalStep.decided_at.is_not(None),
        )
        .values(decided_at=decided)
    )
    if record.request_id is not None:
        asked = record.order_date - timedelta(days=REQUEST_LEAD_DAYS)
        await db.execute(
            update(PurchaseRequest)
            .where(PurchaseRequest.id == record.request_id)
            .values(
                created_at=at(asked, MORNING),
                submitted_at=at(asked, NOON),
                decided_at=at(asked + timedelta(days=1), AFTERNOON),
            )
        )


async def _date_receipt(db: AsyncSession, record: OrderRecord) -> None:
    if record.received_on is None:
        return
    await db.execute(
        update(GoodsReceipt)
        .where(GoodsReceipt.po_id == record.po_id)
        .values(received_at=at(record.received_on, AFTERNOON))
    )
    on_time = literal(DeliveryStatus.ON_TIME, Delivery.status.type)
    on_time_or_late = case(
        (Delivery.expected_date.is_(None), on_time),
        (Delivery.expected_date >= record.received_on, on_time),
        else_=literal(DeliveryStatus.DELAYED, Delivery.status.type),
    )
    await db.execute(
        update(Delivery)
        .where(Delivery.po_id == record.po_id, Delivery.status.in_([DeliveryStatus.ON_TIME, DeliveryStatus.DELAYED]))
        .values(actual_date=record.received_on, status=on_time_or_late)
    )
    await db.execute(
        update(Delivery)
        .where(Delivery.po_id == record.po_id, Delivery.status == DeliveryStatus.PARTIAL)
        .values(actual_date=record.received_on)
    )


async def _date_invoices(db: AsyncSession) -> None:
    """Invoices were recorded on their invoice date, submitted that afternoon and approved a few days later."""
    invoice_day = cast(SupplierInvoice.invoice_date, DateTime(timezone=True))
    await db.execute(
        update(SupplierInvoice).values(
            created_at=invoice_day + timedelta(hours=MORNING.hour),
            submitted_at=case(
                (SupplierInvoice.submitted_at.is_not(None), invoice_day + timedelta(hours=AFTERNOON.hour)),
                else_=None,
            ),
            approved_at=case(
                (
                    SupplierInvoice.approved_at.is_not(None),
                    func.least(invoice_day + timedelta(days=INVOICE_APPROVAL_DAYS, hours=NOON.hour), func.now()),
                ),
                else_=None,
            ),
        )
    )


async def apply_timeline(session_factory: async_sessionmaker[AsyncSession], records: list[OrderRecord]) -> None:
    async with session_factory() as db:
        for record in records:
            await _date_order(db, record)
            await _date_receipt(db, record)
        await _date_invoices(db)
        await db.commit()
