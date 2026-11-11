"""What the demo year looks like, decided before anything is created: pure functions of a seed and today's date.

The plan is deterministic (a seeded random generator), so two runs on the same day build the same company. Nothing
here touches the database or the API.
"""

import random
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.demo.catalog import PRODUCTS, SUPPLIERS, ProductSpec, SupplierSpec

SEED = 96
MONTHS = 12
ORDERS_PER_MONTH = 3
LARGE_PRICE = Decimal(300)
MID_PRICE = Decimal(50)
RECENT_MONTHS = 2
REQUEST_SHARE = 0.4
MAX_LINES_PER_ORDER = 3
# Fates of a regular order: how far through procure-to-pay it got.
PAID, APPROVED, MATCHED, RECEIVED, ORDERED, PENDING, DRAFT = (
    "paid",
    "approved",
    "matched",
    "received",
    "ordered",
    "pending",
    "draft",
)
CURRENT_MONTH_FATES = (ORDERED, PENDING, DRAFT, RECEIVED, MATCHED, ORDERED)
DAY_OF_MONTH_CHOICES = tuple(range(3, 26))
LEAD_DAY_CHOICES = (5, 7, 9, 12, 14)
USD_ONLY_REQUESTS = "USD"


@dataclass(frozen=True)
class LinePlan:
    product: ProductSpec
    quantity: int


@dataclass(frozen=True)
class OrderPlan:
    supplier: SupplierSpec
    lines: tuple[LinePlan, ...]
    order_date: date
    lead_days: int
    fate: str
    # Raised as an employee's purchase request first (only for US-dollar suppliers, whose orders carry no tax).
    via_request: bool = False

    @property
    def delivery_date(self) -> date:
        return self.order_date + timedelta(days=self.lead_days)

    @property
    def net_total(self) -> Decimal:
        return sum((line.product.price * line.quantity for line in self.lines), Decimal(0))


def months_back(today: date, months: int, day: int) -> date:
    """A date ``months`` calendar months before today's month, on ``day`` (never in the future)."""
    index = today.year * 12 + (today.month - 1) - months
    year, month = divmod(index, 12)
    return min(date(year, month + 1, day), today - timedelta(days=1))


def _quantity(rng: random.Random, product: ProductSpec) -> int:
    if product.price >= LARGE_PRICE:
        return rng.randint(2, 12)
    if product.price >= MID_PRICE:
        return rng.randint(5, 40)
    return rng.randint(20, 240)


def _fate(rng: random.Random, months: int, slot: int) -> str:
    if months == 0:
        return CURRENT_MONTH_FATES[slot % len(CURRENT_MONTH_FATES)]
    if months <= RECENT_MONTHS:
        return rng.choice((PAID, APPROVED, MATCHED, PAID, RECEIVED if months == 1 and slot == 0 else MATCHED))
    return rng.choices((PAID, APPROVED), weights=(88, 12))[0]


def _lines(rng: random.Random, supplier: SupplierSpec, seen_totals: set[tuple[str, Decimal]]) -> tuple[LinePlan, ...]:
    catalogue = [product for product in PRODUCTS if product.supplier == supplier.name]
    chosen = rng.sample(catalogue, k=rng.randint(1, min(MAX_LINES_PER_ORDER, len(catalogue))))
    lines = [LinePlan(product, _quantity(rng, product)) for product in chosen]
    # Two invoices from one supplier for the same total within a week look like a duplicate to the matcher, so
    # every order gets a total of its own.
    while (supplier.name, sum((line.product.price * line.quantity for line in lines), Decimal(0))) in seen_totals:
        lines[0] = LinePlan(lines[0].product, lines[0].quantity + 1)
    seen_totals.add((supplier.name, sum((line.product.price * line.quantity for line in lines), Decimal(0))))
    return tuple(lines)


def build_order_plans(today: date, seed: int = SEED) -> tuple[OrderPlan, ...]:
    """Three regular orders a month for the last twelve months, oldest first."""
    rng = random.Random(seed)  # noqa: S311 - a reproducible demo schedule, not a secret
    seen_totals: set[tuple[str, Decimal]] = set()
    plans: list[OrderPlan] = []
    for months in range(MONTHS - 1, -1, -1):
        for slot in range(ORDERS_PER_MONTH):
            supplier = rng.choice(SUPPLIERS)
            order_date = months_back(today, months, rng.choice(DAY_OF_MONTH_CHOICES))
            plans.append(
                OrderPlan(
                    supplier=supplier,
                    lines=_lines(rng, supplier, seen_totals),
                    order_date=order_date,
                    lead_days=rng.choice(LEAD_DAY_CHOICES),
                    fate=_fate(rng, months, slot),
                    via_request=supplier.currency_code == USD_ONLY_REQUESTS and rng.random() < REQUEST_SHARE,
                )
            )
    return tuple(sorted(plans, key=lambda plan: plan.order_date))
