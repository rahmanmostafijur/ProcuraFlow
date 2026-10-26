"""The only place business numbers are computed.

Every figure on the dashboard, in reports, in badges and in exports comes from a function here, with one
definition per metric (see docs/metrics.md for name, formula, period, time zone and statuses). A screen that
needs a number calls this module; it never re-derives it, so two screens cannot disagree.

Amounts are in the company's base currency. Orders are converted once, at approval, using the exchange rate
in force that day, and the converted amount is stored; reports read the stored amount, so they never move.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import ColumnElement, Date, Row, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import today_in
from app.core.fiscal import fiscal_year_bounds, fiscal_year_of
from app.models.budget import Budget, CostCentre
from app.models.company_settings import CompanySettings
from app.models.currency import Currency
from app.models.delivery import Delivery
from app.models.enums import COMMITTED_PO_STATUSES, DeliveryStatus, InvoiceStatus, POStatus
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice
from app.models.user import User
from app.schemas.dashboard import DashboardSummary
from app.services.company_settings_service import get_company_settings
from app.services.invoice_queries import InvoiceFilter

# Orders still moving through the process: not yet received and not cancelled.
PENDING_PO_STATUSES = (
    POStatus.DRAFT,
    POStatus.SUBMITTED,
    POStatus.APPROVED,
    POStatus.ORDERED,
    POStatus.PARTIALLY_RECEIVED,
)
COMPLETED_PO_STATUSES = (POStatus.RECEIVED,)
# Invoices that wait for a person: matched ones for approval, exceptions for a decision.
ATTENTION_INVOICE_STATUSES = (InvoiceStatus.MATCHED, InvoiceStatus.EXCEPTION)
# A month of trend data is looked back over this many days, so a partial current month is always included.
DAYS_PER_TREND_MONTH = 31
HUNDRED = Decimal(100)
ONE_DECIMAL = Decimal("0.1")


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
    fiscal_year_start_month: int
    budget_warn_percent: Decimal

    @classmethod
    def from_settings(cls, settings: CompanySettings) -> "MetricsContext":
        return cls(
            time_zone=settings.timezone,
            base_currency_code=settings.base_currency_code,
            today=today_in(settings.timezone),
            fiscal_year_start_month=settings.fiscal_year_start_month,
            budget_warn_percent=settings.budget_warn_percent,
        )

    @property
    def fiscal_year(self) -> int:
        """The fiscal year today falls in."""
        return fiscal_year_of(self.today, self.fiscal_year_start_month)


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


@dataclass(frozen=True)
class BudgetPosition:
    budget_id: int
    cost_centre_id: int
    cost_centre_code: str
    cost_centre_name: str
    fiscal_year: int
    budget: Decimal
    spent: Decimal
    committed: Decimal
    remaining: Decimal
    utilisation_percent: Decimal | None
    health: str


def _health(budget: Decimal, used: Decimal, warn_percent: Decimal) -> str:
    if used > budget:
        return "over"
    if budget > 0 and used * HUNDRED >= budget * warn_percent:
        return "warning"
    return "ok"


def _position(row: Row[tuple[Budget, CostCentre, Decimal, Decimal]], warn_percent: Decimal) -> BudgetPosition:
    budget, cost_centre, spent, committed = row
    used = spent + committed
    utilisation = None if budget.amount == 0 else (used * HUNDRED / budget.amount).quantize(ONE_DECIMAL, ROUND_HALF_UP)
    return BudgetPosition(
        budget_id=budget.id,
        cost_centre_id=cost_centre.id,
        cost_centre_code=cost_centre.code,
        cost_centre_name=cost_centre.name,
        fiscal_year=budget.fiscal_year,
        budget=budget.amount,
        spent=spent,
        committed=committed,
        remaining=budget.amount - used,
        utilisation_percent=utilisation,
        health=_health(budget.amount, used, warn_percent),
    )


async def budget_positions(
    db: AsyncSession, context: MetricsContext, fiscal_year: int, cost_centre_id: int | None = None
) -> list[BudgetPosition]:
    """Budget, spent, committed and remaining per cost centre for one fiscal year, in the base currency.

    Spent is orders fully received; committed is orders approved, ordered or partially received. An order belongs
    to the fiscal year of its approval date (its creation date if it has none) in the company time zone, and to the
    cost centre it is charged to. Both use the order's stored base grand total (tax included).
    """
    start, end = fiscal_year_bounds(fiscal_year, context.fiscal_year_start_month)
    order_day = cast(
        func.timezone(context.time_zone, func.coalesce(PurchaseOrder.approved_at, PurchaseOrder.created_at)), Date
    )
    spent = func.coalesce(
        func.sum(case((PurchaseOrder.status == POStatus.RECEIVED, PurchaseOrder.base_grand_total), else_=0)), 0
    )
    committed = func.coalesce(
        func.sum(
            case(
                (
                    PurchaseOrder.status.in_((POStatus.APPROVED, POStatus.ORDERED, POStatus.PARTIALLY_RECEIVED)),
                    PurchaseOrder.base_grand_total,
                ),
                else_=0,
            )
        ),
        0,
    )
    stmt = (
        select(Budget, CostCentre, spent.label("spent"), committed.label("committed"))
        .join(CostCentre, CostCentre.id == Budget.cost_centre_id)
        .outerjoin(
            PurchaseOrder,
            (PurchaseOrder.cost_centre_id == Budget.cost_centre_id)
            & PurchaseOrder.status.in_(COMMITTED_PO_STATUSES)
            & (order_day >= start)
            & (order_day < end),
        )
        .where(Budget.fiscal_year == fiscal_year)
        .group_by(Budget.id, CostCentre.id)
        .order_by(CostCentre.code)
    )
    if cost_centre_id is not None:
        stmt = stmt.where(Budget.cost_centre_id == cost_centre_id)
    return [_position(row, context.budget_warn_percent) for row in (await db.execute(stmt)).all()]


async def pending_approval_count(db: AsyncSession, user: User) -> int:
    """How many documents wait for this user's decision: the same list the approvals queue shows."""
    from app.services.approval_queue_service import queue_for  # noqa: PLC0415 - imported here to break an import cycle

    return len(await queue_for(db, user))


async def invoice_counts_by_status(db: AsyncSession, flt: InvoiceFilter | None = None) -> dict[InvoiceStatus, int]:
    """Number of supplier invoices per status (every status present, zero when none), narrowed by the filter."""
    stmt = select(SupplierInvoice.status, func.count()).group_by(SupplierInvoice.status)
    for condition in (flt or InvoiceFilter()).conditions():
        stmt = stmt.where(condition)
    counts = {invoice_status: 0 for invoice_status in InvoiceStatus}
    for invoice_status, count in (await db.execute(stmt)).all():
        counts[invoice_status] = count
    return counts


def needing_attention_from(counts: dict[InvoiceStatus, int]) -> int:
    return sum(counts[invoice_status] for invoice_status in ATTENTION_INVOICE_STATUSES)


async def invoices_needing_attention(db: AsyncSession, flt: InvoiceFilter | None = None) -> int:
    """Matched plus exception invoices: the ones someone still has to approve or decide."""
    return needing_attention_from(await invoice_counts_by_status(db, flt))


async def _payables(
    db: AsyncSession, context: MetricsContext, flt: InvoiceFilter | None, *extra: ColumnElement[bool]
) -> Decimal:
    base_units = await db.scalar(select(Currency.minor_units).where(Currency.code == context.base_currency_code))
    open_base = func.round(
        (SupplierInvoice.grand_total - SupplierInvoice.paid_total) * SupplierInvoice.exchange_rate, base_units
    )
    stmt = select(func.coalesce(func.sum(open_base), 0)).where(
        SupplierInvoice.status == InvoiceStatus.APPROVED, SupplierInvoice.exchange_rate.is_not(None), *extra
    )
    for condition in (flt or InvoiceFilter()).conditions():
        stmt = stmt.where(condition)
    return Decimal((await db.execute(stmt)).scalar_one())


async def payables_outstanding(db: AsyncSession, context: MetricsContext, flt: InvoiceFilter | None = None) -> Decimal:
    """What is still owed on approved, non-void invoices, in the base currency.

    Each invoice's open amount (total - paid) is converted at the rate it locked at approval and rounded to the base
    currency's minor units, then summed. Invoices on hold, void, paid or not yet approved are not counted.
    """
    return await _payables(db, context, flt)


async def payables_overdue(db: AsyncSession, context: MetricsContext, flt: InvoiceFilter | None = None) -> Decimal:
    """Payables outstanding restricted to invoices whose due date is before today in the company time zone."""
    return await _payables(db, context, flt, SupplierInvoice.due_date < context.today)


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
        payables_outstanding=await payables_outstanding(db, context),
        payables_overdue=await payables_overdue(db, context),
        invoices_needing_attention=await invoices_needing_attention(db),
    )
