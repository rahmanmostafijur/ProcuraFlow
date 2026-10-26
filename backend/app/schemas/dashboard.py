from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import Money


class DashboardSummary(BaseModel):
    total_purchase_orders: int
    pending_orders: int
    completed_orders: int
    supplier_count: int
    inventory_value: Money
    low_stock_products: int
    upcoming_deliveries: int
    # Base currency; approved supplier invoices, converted at the rate locked at approval.
    payables_outstanding: Money
    payables_overdue: Money
    # Matched plus exception invoices.
    invoices_needing_attention: int


class MonthlyTrendPoint(BaseModel):
    month: str
    total_spend: Money
    order_count: int


class SupplierPerformanceRow(BaseModel):
    supplier_id: int
    supplier_name: str
    order_count: int
    total_spend: Money


class RecentActivityItem(BaseModel):
    id: int
    action: str
    entity_type: str
    entity_id: int | None
    created_at: datetime
    user_name: str | None
