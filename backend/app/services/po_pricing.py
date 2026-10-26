"""Pricing of purchase order lines and the base-currency lock at approval.

Every stored PO amount is produced here from the money rules in ``app.core.money``: each line is rounded once to
the PO currency, document totals are sums of those lines, and approval converts the totals into the base currency
at the rate in force that day and stores it, so reports in the base currency can never move afterwards.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import today_in
from app.core.money import DocumentTotals, LineAmounts, compute_line, convert_to_base, sum_lines
from app.models.currency import Currency
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.supplier import Supplier
from app.models.tax_rate import TaxRate
from app.services.company_settings_service import get_company_settings
from app.services.currency_service import get_active_currency, get_rate_in_force, lock_rate_value


@dataclass(frozen=True)
class TaxSnapshot:
    """The tax a line was priced with, copied from a tax rate so later edits to the rate change nothing."""

    rate_id: int | None
    name: str | None
    percent: Decimal
    inclusive: bool
    reverse_charge: bool


NO_TAX = TaxSnapshot(rate_id=None, name=None, percent=Decimal(0), inclusive=False, reverse_charge=False)


@dataclass(frozen=True)
class LineSpec:
    product_id: int
    quantity: int
    unit_price: Decimal
    tax: TaxSnapshot = NO_TAX


async def resolve_tax_snapshots(db: AsyncSession, tax_rate_ids: Iterable[int]) -> dict[int, TaxSnapshot]:
    """Snapshots for the requested rates; a rate that is unknown or switched off cannot be put on a line."""
    wanted = set(tax_rate_ids)
    if not wanted:
        return {}
    rows = (await db.execute(select(TaxRate).where(TaxRate.id.in_(wanted)))).scalars().all()
    found = {row.id: row for row in rows}
    unusable = sorted(rate_id for rate_id in wanted if rate_id not in found or not found[rate_id].is_active)
    if unusable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown or inactive tax rate ids: {unusable}"
        )
    return {
        rate_id: TaxSnapshot(
            rate_id=rate_id,
            name=row.name,
            percent=row.percentage,
            inclusive=row.is_inclusive,
            reverse_charge=row.is_reverse_charge,
        )
        for rate_id, row in found.items()
    }


def specs_from_items(items: Iterable[PurchaseOrderItem]) -> list[LineSpec]:
    """Lines as they are stored, with the tax they were originally priced with."""
    return [
        LineSpec(
            product_id=item.product_id,
            quantity=item.quantity,
            unit_price=item.unit_price,
            tax=TaxSnapshot(
                rate_id=item.tax_rate_id,
                name=item.tax_name,
                percent=item.tax_percent,
                inclusive=item.tax_inclusive,
                reverse_charge=item.reverse_charge,
            ),
        )
        for item in items
    ]


def price_lines(specs: Sequence[LineSpec], currency: Currency) -> tuple[list[PurchaseOrderItem], DocumentTotals]:
    items: list[PurchaseOrderItem] = []
    amounts: list[LineAmounts] = []
    for spec in specs:
        line = compute_line(
            quantity=spec.quantity,
            unit_price=spec.unit_price,
            tax_percent=spec.tax.percent,
            tax_inclusive=spec.tax.inclusive,
            minor_units=currency.minor_units,
        )
        amounts.append(line)
        items.append(
            PurchaseOrderItem(
                product_id=spec.product_id,
                quantity=spec.quantity,
                unit_price=spec.unit_price,
                tax_rate_id=spec.tax.rate_id,
                tax_name=spec.tax.name,
                tax_percent=spec.tax.percent,
                tax_inclusive=spec.tax.inclusive,
                reverse_charge=spec.tax.reverse_charge,
                line_net=line.net,
                line_tax=line.tax,
                line_total=line.total,
            )
        )
    return items, sum_lines(amounts)


def apply_totals(po: PurchaseOrder, totals: DocumentTotals) -> None:
    po.subtotal = totals.subtotal
    po.tax_total = totals.tax_total
    po.grand_total = totals.grand_total


async def resolve_currency(db: AsyncSession, requested: str | None, supplier: Supplier) -> Currency:
    """Requested currency, else the supplier's default, else the company's base currency."""
    code = requested or supplier.currency_code or (await get_company_settings(db)).base_currency_code
    return await get_active_currency(db, code)


async def to_base_amount(db: AsyncSession, amount: Decimal, currency_code: str) -> Decimal:
    """An amount in the base currency, converted at the rate in force today in the company time zone.

    Used to match approval rules and limits, which are written in the base currency. A foreign-currency amount with
    no rate on or before today is refused with the same message as approval, so it is caught as early as possible.
    """
    settings = await get_company_settings(db)
    base_code = settings.base_currency_code
    if currency_code == base_code:
        return amount
    today = today_in(settings.timezone)
    rate = lock_rate_value(
        await get_rate_in_force(db, base_code, currency_code, today), currency_code, base_code, today
    )
    base_currency = await db.get(Currency, base_code)
    assert base_currency is not None  # noqa: S101 - the settings row references it by foreign key
    return convert_to_base(amount, rate, base_currency.minor_units)


async def locked_rate_today(db: AsyncSession, currency_code: str) -> Decimal:
    """The exchange rate (base units per one unit of ``currency_code``) in force today in the company time zone.

    A foreign currency with no rate on or before today is refused with the same message everywhere a document locks.
    """
    settings = await get_company_settings(db)
    base_code = settings.base_currency_code
    today = today_in(settings.timezone)
    rate_row = None
    if currency_code != base_code:
        rate_row = await get_rate_in_force(db, base_code, currency_code, today)
    return lock_rate_value(rate_row, currency_code, base_code, today)


async def base_totals(
    db: AsyncSession, subtotal: Decimal, tax_total: Decimal, rate: Decimal
) -> tuple[Decimal, Decimal, Decimal]:
    """Base-currency subtotal, tax and grand total of a document, converted at its locked rate."""
    base_code = (await get_company_settings(db)).base_currency_code
    base_currency = await db.get(Currency, base_code)
    assert base_currency is not None  # noqa: S101 - the settings row references it by foreign key
    base_subtotal = convert_to_base(subtotal, rate, base_currency.minor_units)
    base_tax_total = convert_to_base(tax_total, rate, base_currency.minor_units)
    return base_subtotal, base_tax_total, base_subtotal + base_tax_total


async def lock_base_amounts(db: AsyncSession, po: PurchaseOrder) -> None:
    """Freeze the order's base-currency amounts at approval using the rate in force today (company time zone)."""
    po.exchange_rate = await locked_rate_today(db, po.currency_code)
    await refresh_base_amounts(db, po)


async def refresh_base_amounts(db: AsyncSession, po: PurchaseOrder) -> None:
    """Recompute the base-currency amounts from the order's totals at the rate it locked at approval.

    Used when an amendment changes the totals: the order keeps its original rate, so only the amounts move.
    """
    assert po.exchange_rate is not None  # noqa: S101 - only approved orders have amounts to refresh
    po.base_subtotal, po.base_tax_total, po.base_grand_total = await base_totals(
        db, po.subtotal, po.tax_total, po.exchange_rate
    )
