"""Booking a delivery against a purchase order: accepted units enter stock, rejected units stay open on the order."""

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.clock import utc_today
from app.models.enums import DeliveryStatus, InventoryTransactionType, POStatus, ReceiptCondition
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptLine
from app.models.purchase_order import PurchaseOrder
from app.services.inventory_service import apply_inventory_transaction, lock_products

RECEIVABLE_STATUSES = (POStatus.ORDERED, POStatus.PARTIALLY_RECEIVED)


@dataclass(frozen=True)
class ReceiptInput:
    product_id: int
    delivered: int
    rejected: int = 0
    condition: ReceiptCondition = ReceiptCondition.GOOD
    note: str | None = None

    @property
    def accepted(self) -> int:
        return self.delivered - self.rejected


def _bad_request(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


def _check_lines(po: PurchaseOrder, lines: list[ReceiptInput]) -> None:
    items_by_product = {item.product_id: item for item in po.items}
    for line in lines:
        item = items_by_product.get(line.product_id)
        if item is None:
            raise _bad_request(f"Product {line.product_id} is not on this purchase order")
        remaining = item.quantity - item.received_quantity
        if line.accepted > remaining:
            raise _bad_request(
                f"Cannot receive {line.accepted} units of product {line.product_id}; only {remaining} remain"
            )


def _update_delivery(po: PurchaseOrder, total_ordered: int, total_received: int) -> None:
    if po.delivery is None or total_received == 0:
        return
    po.delivery.received_quantity = total_received
    po.delivery.actual_date = utc_today()
    if total_received >= total_ordered:
        is_on_time = po.delivery.expected_date is None or po.delivery.actual_date <= po.delivery.expected_date
        po.delivery.status = DeliveryStatus.ON_TIME if is_on_time else DeliveryStatus.DELAYED
    else:
        po.delivery.status = DeliveryStatus.PARTIAL


async def receive_goods(
    db: AsyncSession, po: PurchaseOrder, lines: list[ReceiptInput], received_by: int, note: str | None = None
) -> GoodsReceipt:
    """Record a delivery. The caller must hold the order's row lock and commits.

    Only accepted units (delivered minus rejected) go through the inventory ledger and count toward the line's
    received quantity, so rejected units stay open on the order and can still be delivered later. The order is
    received once the accepted units reach what was ordered.
    """
    if po.status not in RECEIVABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot receive stock for a purchase order in status '{po.status.value}'",
        )
    _check_lines(po, lines)

    items_by_product = {item.product_id: item for item in po.items}
    accepted = {line.product_id: line.accepted for line in lines if line.accepted > 0}
    products = await lock_products(db, accepted)
    for product_id, quantity in accepted.items():
        await apply_inventory_transaction(
            db,
            product=products[product_id],
            quantity_delta=quantity,
            transaction_type=InventoryTransactionType.PO_RECEIPT,
            created_by=received_by,
            reference_po_id=po.id,
            reason=f"Receipt against {po.po_number}",
        )
        items_by_product[product_id].received_quantity += quantity

    receipt = GoodsReceipt(po_id=po.id, received_by=received_by, note=note)
    receipt.lines = [
        GoodsReceiptLine(
            product_id=line.product_id,
            delivered_quantity=line.delivered,
            accepted_quantity=line.accepted,
            rejected_quantity=line.rejected,
            condition=line.condition,
            note=line.note,
        )
        for line in lines
    ]
    db.add(receipt)

    total_ordered = sum(item.quantity for item in po.items)
    total_received = sum(item.received_quantity for item in po.items)
    _update_delivery(po, total_ordered, total_received)
    if total_received >= total_ordered:
        po.status = POStatus.RECEIVED
    elif total_received > 0:
        po.status = POStatus.PARTIALLY_RECEIVED
    await db.flush()
    return receipt


async def list_receipts(db: AsyncSession, po_id: int) -> list[GoodsReceipt]:
    """The order's deliveries, oldest first."""
    stmt = (
        select(GoodsReceipt)
        .options(selectinload(GoodsReceipt.lines), selectinload(GoodsReceipt.receiver))
        .where(GoodsReceipt.po_id == po_id)
        .order_by(GoodsReceipt.id)
        .execution_options(populate_existing=True)
    )
    return list((await db.execute(stmt)).scalars().all())
