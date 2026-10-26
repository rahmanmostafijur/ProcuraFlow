"""Returning rejected goods to the supplier: what may be returned, and the forward-only status of the return."""

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from app.models.enums import ReturnStatus
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptLine, SupplierReturn
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.user import User
from app.schemas.person import PersonRead
from app.schemas.supplier_return import SupplierReturnCreate, SupplierReturnRead, SupplierReturnStatusChange
from app.services.audit_service import record_audit_event
from app.services.purchase_order_service import get_purchase_order_for_update

_ALLOWED: dict[ReturnStatus, set[ReturnStatus]] = {
    ReturnStatus.OPEN: {ReturnStatus.SENT, ReturnStatus.CANCELLED},
    ReturnStatus.SENT: {ReturnStatus.RESOLVED, ReturnStatus.CANCELLED},
    ReturnStatus.RESOLVED: set(),
    ReturnStatus.CANCELLED: set(),
}
LOAD = (
    selectinload(SupplierReturn.purchase_order).selectinload(PurchaseOrder.supplier),
    selectinload(SupplierReturn.product),
    selectinload(SupplierReturn.creator),
)


def to_read(row: SupplierReturn) -> SupplierReturnRead:
    return SupplierReturnRead(
        id=row.id,
        po_id=row.po_id,
        po_number=row.purchase_order.po_number,
        supplier_id=row.purchase_order.supplier_id,
        supplier_name=row.purchase_order.supplier.name,
        product_id=row.product_id,
        product_sku=row.product.sku,
        product_name=row.product.name,
        quantity=row.quantity,
        reason=row.reason,
        resolution=row.resolution,
        status=row.status,
        created_by=PersonRead(id=row.creator.id, full_name=row.creator.full_name),
        resolved_at=row.resolved_at,
        note=row.note,
        created_at=row.created_at,
    )


async def returnable_quantity(db: AsyncSession, po_id: int, product_id: int) -> int:
    """Rejected units of the product on the order that are not yet on a (non-cancelled) return."""
    rejected = await db.scalar(
        select(func.coalesce(func.sum(GoodsReceiptLine.rejected_quantity), 0))
        .join(GoodsReceipt, GoodsReceipt.id == GoodsReceiptLine.receipt_id)
        .where(GoodsReceipt.po_id == po_id, GoodsReceiptLine.product_id == product_id)
    )
    returned = await db.scalar(
        select(func.coalesce(func.sum(SupplierReturn.quantity), 0)).where(
            SupplierReturn.po_id == po_id,
            SupplierReturn.product_id == product_id,
            SupplierReturn.status != ReturnStatus.CANCELLED,
        )
    )
    return int(rejected or 0) - int(returned or 0)


async def get_return(db: AsyncSession, return_id: int, *, for_update: bool = False) -> SupplierReturn:
    stmt = select(SupplierReturn).options(*LOAD).where(SupplierReturn.id == return_id)
    if for_update:
        stmt = stmt.with_for_update(of=SupplierReturn)
    row = await db.scalar(stmt.execution_options(populate_existing=True))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Return not found")
    return row


def list_statement(
    status_filter: ReturnStatus | None, po_id: int | None, supplier_id: int | None
) -> Select[tuple[SupplierReturn]]:
    stmt = select(SupplierReturn).options(*LOAD).order_by(SupplierReturn.id.desc())
    if status_filter is not None:
        stmt = stmt.where(SupplierReturn.status == status_filter)
    if po_id is not None:
        stmt = stmt.where(SupplierReturn.po_id == po_id)
    if supplier_id is not None:
        supplier_orders = select(PurchaseOrder.id).where(PurchaseOrder.supplier_id == supplier_id)
        stmt = stmt.where(SupplierReturn.po_id.in_(supplier_orders))
    return stmt


async def create_return(db: AsyncSession, payload: SupplierReturnCreate, actor: User) -> SupplierReturn:
    # The order's row lock serialises returns for the same order, so two requests cannot claim the same units.
    await get_purchase_order_for_update(db, payload.po_id)
    if await db.get(Product, payload.product_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Product not found")
    available = max(await returnable_quantity(db, payload.po_id, payload.product_id), 0)
    if payload.quantity > available:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Cannot return {payload.quantity} units; only {available} rejected units are not yet returned",
        )
    row = SupplierReturn(
        po_id=payload.po_id,
        product_id=payload.product_id,
        quantity=payload.quantity,
        reason=payload.reason,
        resolution=payload.resolution,
        status=ReturnStatus.OPEN,
        created_by=actor.id,
        note=payload.note,
    )
    db.add(row)
    await db.flush()
    await record_audit_event(
        db,
        user_id=actor.id,
        action="supplier_return_created",
        entity_type="supplier_return",
        entity_id=row.id,
        extra_data={
            "po_id": row.po_id,
            "product_id": row.product_id,
            "quantity": row.quantity,
            "resolution": row.resolution.value,
        },
    )
    await db.commit()
    return await get_return(db, row.id)


async def change_status(
    db: AsyncSession, return_id: int, payload: SupplierReturnStatusChange, actor: User
) -> SupplierReturn:
    row = await get_return(db, return_id, for_update=True)
    if payload.status not in _ALLOWED[row.status]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot move a return from '{row.status.value}' to '{payload.status.value}'",
        )
    previous = row.status
    row.status = payload.status
    if payload.status == ReturnStatus.RESOLVED:
        row.resolved_at = datetime.now(UTC)
    if payload.note is not None:
        row.note = payload.note
    await record_audit_event(
        db,
        user_id=actor.id,
        action="supplier_return_status_changed",
        entity_type="supplier_return",
        entity_id=row.id,
        extra_data={"from": previous.value, "to": payload.status.value, "note": payload.note},
    )
    await db.commit()
    return await get_return(db, return_id)
