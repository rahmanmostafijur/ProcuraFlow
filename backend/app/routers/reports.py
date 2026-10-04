import csv
import io

from fastapi import APIRouter, Response
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser, DbSession
from app.models.delivery import Delivery
from app.models.enums import COMMITTED_PO_STATUSES, DeliveryStatus
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.supplier import Supplier
from app.services.delivery_service import get_on_time_delivery_rate

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/supplier-performance")
async def supplier_performance(db: DbSession, _: CurrentUser) -> list[dict]:
    line_total = PurchaseOrderItem.quantity * PurchaseOrderItem.unit_price
    stmt = (
        select(
            Supplier.id,
            Supplier.name,
            func.count(func.distinct(PurchaseOrder.id)).label("order_count"),
            func.coalesce(func.sum(line_total), 0).label("total_spend"),
        )
        # The status filter sits in the join so suppliers without committed orders still get a zero row.
        .outerjoin(
            PurchaseOrder,
            (PurchaseOrder.supplier_id == Supplier.id) & PurchaseOrder.status.in_(COMMITTED_PO_STATUSES),
        )
        .outerjoin(PurchaseOrderItem, PurchaseOrderItem.po_id == PurchaseOrder.id)
        .group_by(Supplier.id, Supplier.name)
        .order_by(Supplier.name)
    )
    result = await db.execute(stmt)
    return [
        {
            "supplier_id": row.id,
            "supplier_name": row.name,
            "order_count": row.order_count,
            "total_spend": row.total_spend,
        }
        for row in result
    ]


@router.get("/delayed-deliveries")
async def delayed_deliveries(db: DbSession, _: CurrentUser) -> list[dict]:
    stmt = (
        select(Delivery)
        .options(selectinload(Delivery.purchase_order).selectinload(PurchaseOrder.supplier))
        .where(Delivery.status == DeliveryStatus.DELAYED)
        .order_by(Delivery.actual_date.desc())
    )
    result = await db.execute(stmt)
    deliveries = result.scalars().all()
    return [
        {
            "po_number": d.purchase_order.po_number,
            "supplier_name": d.purchase_order.supplier.name,
            "expected_date": d.expected_date,
            "actual_date": d.actual_date,
            "variance_days": (
                (d.actual_date - d.expected_date).days if d.expected_date and d.actual_date else None
            ),
        }
        for d in deliveries
    ]


@router.get("/on-time-delivery-rate")
async def on_time_delivery_rate(db: DbSession, _: CurrentUser) -> dict:
    return {"on_time_percentage": await get_on_time_delivery_rate(db)}


@router.get("/inventory-status.csv")
async def inventory_status_csv(db: DbSession, _: CurrentUser) -> Response:
    result = await db.execute(select(Product).order_by(Product.sku))
    products = result.scalars().all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["SKU", "Name", "Current Stock", "Minimum Stock", "Cost", "Stock Value", "Low Stock"])
    for p in products:
        writer.writerow(
            [p.sku, p.name, p.current_stock, p.minimum_stock, p.cost, p.current_stock * p.cost,
             p.current_stock <= p.minimum_stock]
        )

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=inventory-status.csv"},
    )
