from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    total_purchase_orders: int
    pending_orders: int
    completed_orders: int
    supplier_count: int
    inventory_value: Decimal
    low_stock_products: int
    upcoming_deliveries: int


class MonthlyTrendPoint(BaseModel):
    month: str
    total_spend: Decimal
    order_count: int


class RecentActivityItem(BaseModel):
    id: int
    action: str
    entity_type: str
    entity_id: int | None
    created_at: datetime
    user_name: str | None
