from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.clock import utc_today
from app.models.delivery import Delivery
from app.models.enums import DeliveryStatus, InventoryTransactionType, POStatus
from app.models.purchase_order import PO_NUMBER_SEQUENCE, PurchaseOrder
from app.models.role import Role
from app.models.user import User
from app.services import approval_adapters, approval_engine
from app.services.company_settings_service import get_company_settings
from app.services.inventory_service import apply_inventory_transaction, lock_products
from app.services.po_pricing import to_base_amount

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


def ensure_transition_allowed(current: POStatus, target: POStatus) -> None:
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
    year = datetime.now(UTC).year
    prefix = (await get_company_settings(db)).po_number_prefix
    number = await db.scalar(select(PO_NUMBER_SEQUENCE.next_value()))
    # The sequence is shared by every prefix, so changing the prefix can never produce a duplicate number.
    return f"{prefix}-{year}-{number:05d}"


async def submit_purchase_order(db: AsyncSession, po: PurchaseOrder) -> None:
    """Send a draft for approval: the amount in the base currency picks the approval rule and opens its steps."""
    ensure_transition_allowed(po.status, POStatus.SUBMITTED)
    amount_base = await to_base_amount(db, po.grand_total, po.currency_code)
    po.status = POStatus.SUBMITTED
    await approval_engine.open_round(db, approval_adapters.po_subject(po, amount_base))


async def decide_purchase_order(
    db: AsyncSession, po: PurchaseOrder, actor: User, *, approve: bool, comment: str | None = None
) -> bool:
    """Approve or reject the order's current approval step; returns whether that settled the order.

    Whether this person may decide (not the creator, not already on an earlier step, right role or permission,
    within their limit, budget rules) is the approval engine's call, the same for every kind of document.
    """
    outcome = await approval_engine.decide(
        db, approval_adapters.po_subject(po), actor, approve=approve, comment=comment
    )
    return outcome.is_final


async def approve_purchase_order(db: AsyncSession, po: PurchaseOrder, approver: User) -> bool:
    return await decide_purchase_order(db, po, approver, approve=True)


def mark_purchase_order_ordered(db: AsyncSession, po: PurchaseOrder) -> None:
    ensure_transition_allowed(po.status, POStatus.ORDERED)
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
    ensure_transition_allowed(po.status, POStatus.CANCELLED)
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
        po.delivery.actual_date = utc_today()
        if total_received >= total_ordered:
            is_on_time = po.delivery.expected_date is None or po.delivery.actual_date <= po.delivery.expected_date
            po.delivery.status = DeliveryStatus.ON_TIME if is_on_time else DeliveryStatus.DELAYED
        else:
            po.delivery.status = DeliveryStatus.PARTIAL

    po.status = POStatus.RECEIVED if total_received >= total_ordered else POStatus.PARTIALLY_RECEIVED
