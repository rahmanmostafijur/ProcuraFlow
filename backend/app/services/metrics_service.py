"""The only place business numbers are computed.

Every figure on the dashboard, in reports, in badges and in exports comes from a function here, with one
definition per metric (see docs/metrics.md for name, formula, period, time zone and statuses). A screen that
needs a number calls this module; it never re-derives it, so two screens cannot disagree.

Amounts are in the company's base currency. Orders are converted once, at approval, using the exchange rate
in force that day, and the converted amount is stored; reports read the stored amount, so they never move.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import today_in
from app.models.company_settings import CompanySettings
from app.models.delivery import Delivery
from app.models.enums import COMMITTED_PO_STATUSES, DeliveryStatus, POStatus
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.supplier import Supplier
from app.schemas.dashboard import DashboardSummary
from app.services.company_settings_service import get_company_settings

# Orders still moving through the process: not yet received and not cancelled.
PENDING_PO_STATUSES = (
    POStatus.DRAFT,
    POStatus.SUBMITTED,
    POStatus.APPROVED,
    POStatus.ORDERED,
    POStatus.PARTIALLY_RECEIVED,
)
COMPLETED_PO_STATUSES = (POStatus.RECEIVED,)
# A month of trend data is looked back over this many days, so a partial current month is always included.
DAYS_PER_TREND_MONTH = 31


@dataclass(frozen=True)
class MonthlySpend:
    month: str
    total_spend: Decimal
    order_count: int


@dataclass(frozen=True)
class SupplierSpend:
    supplier_id: int
    supplier_name: str
    order_count: int
    total_spend: Decimal


@dataclass(frozen=True)
class MetricsContext:
    """The company settings every period-based metric depends on, read once per request."""

    time_zone: str
    base_currency_code: str
    today: date

    @classmethod
    def from_settings(cls, settings: CompanySettings) -> "MetricsContext":
        return cls(
            time_zone=settings.timezone,
            base_currency_code=settings.base_currency_code,
            today=today_in(settings.timezone),
        )


async def get_context(db: AsyncSession) -> MetricsContext:
    return MetricsContext.from_settings(await get_company_settings(db))


async def _count_orders(db: AsyncSession, *statuses: POStatus) -> int:
    stmt = select(func.count()).select_from(PurchaseOrder)
    if statuses:
        stmt = stmt.where(PurchaseOrder.status.in_(statuses))
    return (await db.execute(stmt)).scalar_one()


async def total_purchase_orders(db: AsyncSession) -> int:
    return await _count_orders(db)


async def pending_purchase_orders(db: AsyncSession) -> int:
    return await _count_orders(db, *PENDING_PO_STATUSES)


async def completed_purchase_orders(db: AsyncSession) -> int:
    return await _count_orders(db, *COMPLETED_PO_STATUSES)


async def active_supplier_count(db: AsyncSession) -> int:
    stmt = select(func.count()).select_from(Supplier).where(Supplier.is_active.is_(True))
    return (await db.execute(stmt)).scalar_one()


async def inventory_value(db: AsyncSession) -> Decimal:
    """Sum of unit cost x stock over all products. Product costs are kept in the base currency."""
    stmt = select(func.coalesce(func.sum(Product.cost * Product.current_stock), 0))
    return (await db.execute(stmt)).scalar_one()


async def low_stock_product_count(db: AsyncSession) -> int:
    stmt = (
        select(func.count())
        .select_from(Product)
        .where(Product.current_stock <= Product.minimum_stock, Product.is_active.is_(True))
    )
    return (await db.execute(stmt)).scalar_one()


async def upcoming_delivery_count(db: AsyncSession, context: MetricsContext) -> int:
    """Pending deliveries expected today or later, where "today" is the company's calendar day."""
    stmt = (
        select(func.count())
        .select_from(Delivery)
        .where(Delivery.status == DeliveryStatus.PENDING, Delivery.expected_date >= context.today)
    )
    return (await db.execute(stmt)).scalar_one()


async def committed_spend_by_month(db: AsyncSession, context: MetricsContext, months: int) -> list[MonthlySpend]:
    """Committed spend per calendar month of order creation, in the company time zone.

    Committed means approved, ordered, partially received or received; drafts, submitted and cancelled orders
    never count. The amount is the order's stored base-currency grand total (tax included).
    """
    cutoff = context.today.replace(day=1) - timedelta(days=months * DAYS_PER_TREND_MONTH)
    month_expr = func.to_char(func.timezone(context.time_zone, PurchaseOrder.created_at), "YYYY-MM")
    stmt = (
        select(
            month_expr.label("month"),
            func.coalesce(func.sum(PurchaseOrder.base_grand_total), 0).label("total_spend"),
            func.count(PurchaseOrder.id).label("order_count"),
        )
        .where(PurchaseOrder.created_at >= cutoff, PurchaseOrder.status.in_(COMMITTED_PO_STATUSES))
        .group_by(month_expr)
        .order_by(month_expr)
    )
    return [
        MonthlySpend(month=row.month, total_spend=row.total_spend, order_count=row.order_count)
        for row in await db.execute(stmt)
    ]


async def committed_spend_by_supplier(db: AsyncSession) -> list[SupplierSpend]:
    """Committed spend and order count per supplier, including suppliers that have none yet."""
    stmt = (
        select(
            Supplier.id,
            Supplier.name,
            func.count(PurchaseOrder.id).label("order_count"),
            func.coalesce(func.sum(PurchaseOrder.base_grand_total), 0).label("total_spend"),
        )
        # The status filter sits in the join so suppliers without committed orders still get a zero row.
        .outerjoin(
            PurchaseOrder,
            (PurchaseOrder.supplier_id == Supplier.id) & PurchaseOrder.status.in_(COMMITTED_PO_STATUSES),
        )
        .group_by(Supplier.id, Supplier.name)
        .order_by(Supplier.name)
    )
    return [
        SupplierSpend(
            supplier_id=row.id, supplier_name=row.name, order_count=row.order_count, total_spend=row.total_spend
        )
        for row in await db.execute(stmt)
    ]


async def dashboard_summary(db: AsyncSession) -> DashboardSummary:
    context = await get_context(db)
    return DashboardSummary(
        total_purchase_orders=await total_purchase_orders(db),
        pending_orders=await pending_purchase_orders(db),
        completed_orders=await completed_purchase_orders(db),
        supplier_count=await active_supplier_count(db),
        inventory_value=await inventory_value(db),
        low_stock_products=await low_stock_product_count(db),
        upcoming_deliveries=await upcoming_delivery_count(db, context),
    )
