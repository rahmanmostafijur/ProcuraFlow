import csv
import io
from typing import Any

from fastapi import APIRouter, Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.csv_safety import neutralize_formula
from app.core.deps import CurrentUser, DbSession
from app.models.delivery import Delivery
from app.models.enums import DeliveryStatus
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.schemas.dashboard import SupplierPerformanceRow
from app.services import metrics_service
from app.services.delivery_service import get_on_time_delivery_rate

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/supplier-performance", response_model=list[SupplierPerformanceRow])
async def supplier_performance(db: DbSession, _: CurrentUser) -> list[SupplierPerformanceRow]:
    return [
        SupplierPerformanceRow(
            supplier_id=row.supplier_id,
            supplier_name=row.supplier_name,
            order_count=row.order_count,
            total_spend=row.total_spend,
        )
        for row in await metrics_service.committed_spend_by_supplier(db)
    ]


@router.get("/delayed-deliveries")
async def delayed_deliveries(db: DbSession, _: CurrentUser) -> list[dict[str, Any]]:
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
            "variance_days": ((d.actual_date - d.expected_date).days if d.expected_date and d.actual_date else None),
        }
        for d in deliveries
    ]


@router.get("/on-time-delivery-rate")
async def on_time_delivery_rate(db: DbSession, _: CurrentUser) -> dict[str, float]:
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
            [
                neutralize_formula(p.sku),
                neutralize_formula(p.name),
                p.current_stock,
                p.minimum_stock,
                p.cost,
                p.current_stock * p.cost,
                p.current_stock <= p.minimum_stock,
            ]
        )

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=inventory-status.csv"},
    )
