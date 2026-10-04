from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.delivery import Delivery
from app.models.enums import DeliveryStatus, InventoryTransactionType, POStatus
from app.models.purchase_order import PurchaseOrder
from app.models.role import Role
from app.models.user import User
from app.services.inventory_service import apply_inventory_transaction, lock_products

# Responses serialize creator/approver roles, and a refreshing load resets lazy relationships,
# so load them eagerly instead of relying on objects already in the session.
PO_LOAD_OPTIONS = (
    selectinload(PurchaseOrder.supplier),
    selectinload(PurchaseOrder.items),
    selectinload(PurchaseOrder.creator).selectinload(User.role).selectinload(Role.permissions),
    selectinload(PurchaseOrder.approver).selectinload(User.role).selectinload(Role.permissions),
    selectinload(PurchaseOrder.delivery),
)

_ALLOWED_TRANSITIONS: dict[POStatus, set[POStatus]] = {
    POStatus.DRAFT: {POStatus.SUBMITTED, POStatus.CANCELLED},
    POStatus.SUBMITTED: {POStatus.APPROVED, POStatus.CANCELLED},
    POStatus.APPROVED: {POStatus.ORDERED, POStatus.CANCELLED},
    POStatus.ORDERED: {POStatus.PARTIALLY_RECEIVED, POStatus.RECEIVED, POStatus.CANCELLED},
    POStatus.PARTIALLY_RECEIVED: {POStatus.RECEIVED, POStatus.CANCELLED},
    POStatus.RECEIVED: set(),
    POStatus.CANCELLED: set(),
}


def _ensure_transition_allowed(current: POStatus, target: POStatus) -> None:
    if target not in _ALLOWED_TRANSITIONS.get(current, set()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot transition purchase order from '{current.value}' to '{target.value}'",
        )


async def get_purchase_order_for_update(db: AsyncSession, po_id: int) -> PurchaseOrder:
    result = await db.execute(
        select(PurchaseOrder)
        .options(*PO_LOAD_OPTIONS)
        .where(PurchaseOrder.id == po_id)
        .with_for_update(of=PurchaseOrder)
        .execution_options(populate_existing=True)
    )
    po = result.scalar_one_or_none()
    if po is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
    return po


async def generate_po_number(db: AsyncSession) -> str:
    year = datetime.now(timezone.utc).year
    count = (await db.execute(select(func.count()).select_from(PurchaseOrder))).scalar_one()
    return f"PO-{year}-{count + 1:05d}"


def submit_purchase_order(po: PurchaseOrder) -> None:
    _ensure_transition_allowed(po.status, POStatus.SUBMITTED)
    po.status = POStatus.SUBMITTED


def approve_purchase_order(po: PurchaseOrder, approver: User) -> None:
    _ensure_transition_allowed(po.status, POStatus.APPROVED)
    po.status = POStatus.APPROVED
    po.approved_by = approver.id
    po.approved_at = datetime.now(timezone.utc)


def mark_purchase_order_ordered(db: AsyncSession, po: PurchaseOrder) -> None:
    _ensure_transition_allowed(po.status, POStatus.ORDERED)
    po.status = POStatus.ORDERED

    total_ordered = sum(item.quantity for item in po.items)
    delivery = Delivery(
        po_id=po.id,
        expected_date=po.expected_delivery_date,
        status=DeliveryStatus.PENDING,
        ordered_quantity=total_ordered,
        received_quantity=0,
    )
    db.add(delivery)


def cancel_purchase_order(po: PurchaseOrder) -> None:
    _ensure_transition_allowed(po.status, POStatus.CANCELLED)
    po.status = POStatus.CANCELLED


async def receive_purchase_order_items(
    db: AsyncSession,
    po: PurchaseOrder,
    received_items: dict[int, int],
    received_by: int,
) -> None:
    if po.status not in (POStatus.ORDERED, POStatus.PARTIALLY_RECEIVED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot receive stock for a purchase order in status '{po.status.value}'",
        )

    items_by_product = {item.product_id: item for item in po.items}
    for product_id, quantity in received_items.items():
        item = items_by_product.get(product_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product {product_id} is not on this purchase order",
            )
        remaining = item.quantity - item.received_quantity
        if quantity > remaining:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot receive {quantity} units of product {product_id}; only {remaining} remain",
            )

    products = await lock_products(db, received_items)
    for product_id, quantity in received_items.items():
        item = items_by_product[product_id]
        await apply_inventory_transaction(
            db,
            product=products[product_id],
            quantity_delta=quantity,
            transaction_type=InventoryTransactionType.PO_RECEIPT,
            created_by=received_by,
            reference_po_id=po.id,
            reason=f"Receipt against {po.po_number}",
        )
        item.received_quantity += quantity

    total_ordered = sum(item.quantity for item in po.items)
    total_received = sum(item.received_quantity for item in po.items)

    if po.delivery is not None:
        po.delivery.received_quantity = total_received
        po.delivery.actual_date = date.today()
        if total_received >= total_ordered:
            is_on_time = (
                po.delivery.expected_date is None or po.delivery.actual_date <= po.delivery.expected_date
            )
            po.delivery.status = DeliveryStatus.ON_TIME if is_on_time else DeliveryStatus.DELAYED
        else:
            po.delivery.status = DeliveryStatus.PARTIAL

    po.status = POStatus.RECEIVED if total_received >= total_ordered else POStatus.PARTIALLY_RECEIVED
