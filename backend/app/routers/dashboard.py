from datetime import date, timedelta

from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser, DbSession
from app.models.audit import AuditLog
from app.models.delivery import Delivery
from app.models.enums import DeliveryStatus, POStatus
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.supplier import Supplier
from app.schemas.dashboard import DashboardSummary, MonthlyTrendPoint, RecentActivityItem

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_PENDING_STATUSES = (
    POStatus.DRAFT,
    POStatus.SUBMITTED,
    POStatus.APPROVED,
    POStatus.ORDERED,
    POStatus.PARTIALLY_RECEIVED,
)
_COMPLETED_STATUSES = (POStatus.RECEIVED,)


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(db: DbSession, _: CurrentUser) -> DashboardSummary:
    total_pos = (await db.execute(select(func.count()).select_from(PurchaseOrder))).scalar_one()
    pending = (
        await db.execute(
            select(func.count()).select_from(PurchaseOrder).where(PurchaseOrder.status.in_(_PENDING_STATUSES))
        )
    ).scalar_one()
    completed = (
        await db.execute(
            select(func.count()).select_from(PurchaseOrder).where(PurchaseOrder.status.in_(_COMPLETED_STATUSES))
        )
    ).scalar_one()
    supplier_count = (
        await db.execute(select(func.count()).select_from(Supplier).where(Supplier.is_active.is_(True)))
    ).scalar_one()
    inventory_value = (
        await db.execute(select(func.coalesce(func.sum(Product.current_stock * Product.cost), 0)))
    ).scalar_one()
    low_stock = (
        await db.execute(
            select(func.count())
            .select_from(Product)
            .where(Product.current_stock <= Product.minimum_stock, Product.is_active.is_(True))
        )
    ).scalar_one()
    upcoming_deliveries = (
        await db.execute(
            select(func.count())
            .select_from(Delivery)
            .where(Delivery.status == DeliveryStatus.PENDING, Delivery.expected_date >= date.today())
        )
    ).scalar_one()

    return DashboardSummary(
        total_purchase_orders=total_pos,
        pending_orders=pending,
        completed_orders=completed,
        supplier_count=supplier_count,
        inventory_value=inventory_value,
        low_stock_products=low_stock,
        upcoming_deliveries=upcoming_deliveries,
    )


@router.get("/monthly-trends", response_model=list[MonthlyTrendPoint])
async def get_monthly_trends(db: DbSession, _: CurrentUser, months: int = 6) -> list[MonthlyTrendPoint]:
    cutoff = date.today().replace(day=1) - timedelta(days=months * 31)
    month_expr = func.to_char(PurchaseOrder.created_at, "YYYY-MM")
    line_total = PurchaseOrderItem.quantity * PurchaseOrderItem.unit_price

    stmt = (
        select(
            month_expr.label("month"),
            func.coalesce(func.sum(line_total), 0).label("total_spend"),
            func.count(func.distinct(PurchaseOrder.id)).label("order_count"),
        )
        .join(PurchaseOrderItem, PurchaseOrderItem.po_id == PurchaseOrder.id)
        .where(PurchaseOrder.created_at >= cutoff)
        .group_by(month_expr)
        .order_by(month_expr)
    )
    result = await db.execute(stmt)
    return [
        MonthlyTrendPoint(month=row.month, total_spend=row.total_spend, order_count=row.order_count)
        for row in result
    ]


@router.get("/recent-activity", response_model=list[RecentActivityItem])
async def get_recent_activity(db: DbSession, _: CurrentUser, limit: int = 10) -> list[RecentActivityItem]:
    stmt = (
        select(AuditLog).options(selectinload(AuditLog.user)).order_by(AuditLog.created_at.desc()).limit(limit)
    )
    result = await db.execute(stmt)
    logs = result.scalars().all()
    return [
        RecentActivityItem(
            id=log.id,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            created_at=log.created_at,
            user_name=log.user.full_name if log.user else None,
        )
        for log in logs
    ]
