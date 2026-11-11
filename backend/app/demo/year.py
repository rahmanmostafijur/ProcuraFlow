"""Seed step 4: the regular twelve months, each order taken as far through procure-to-pay as its fate says."""

from dataclasses import dataclass, field
from datetime import date, timedelta

from app.demo.api import DemoApi, DemoSeedError
from app.demo.finance import (
    InvoiceNumbers,
    approve_invoice,
    invoice_lines,
    pay_invoice,
    payment_date,
    record_invoice,
)
from app.demo.plan import APPROVED, DRAFT, MATCHED, ORDERED, PAID, PENDING, RECEIVED, OrderPlan
from app.demo.procure import OrderRecord, Until, advance_order, receipt_date, receive
from app.demo.setup import Foundation

LATE_DELIVERY_EVERY = 4
LATE_DELIVERY_DAYS = 3
UNTIL_BY_FATE: dict[str, Until] = {DRAFT: "draft", PENDING: "submit"}


@dataclass
class SeedContext:
    """What every step needs: the way into the API, the ids created so far and the bookkeeping for later steps."""

    api: DemoApi
    foundation: Foundation
    today: date
    numbers: InvoiceNumbers = field(default_factory=InvoiceNumbers)
    records: list[OrderRecord] = field(default_factory=list)
    sepa_run_number: str | None = None


async def run_plan(ctx: SeedContext, plan: OrderPlan, index: int) -> OrderRecord:
    """Take one planned order as far as its fate says; the record is kept for the timeline step."""
    api, foundation = ctx.api, ctx.foundation
    record = await advance_order(api, foundation, plan, until=UNTIL_BY_FATE.get(plan.fate, "order"))
    ctx.records.append(record)
    if plan.fate in (DRAFT, PENDING, ORDERED):
        return record

    delay = LATE_DELIVERY_DAYS if index % LATE_DELIVERY_EVERY == 0 else 0
    record.received_on = receipt_date(plan, ctx.today, delay)
    await receive(
        api, record.po_id, [(line.product, line.quantity, 0) for line in plan.lines], foundation, "Delivered complete"
    )
    if plan.fate == RECEIVED:
        return record

    invoice_date = min(record.received_on + timedelta(days=1), ctx.today)
    invoice = await record_invoice(
        api, record, invoice_lines(plan.lines, foundation), ctx.numbers.next(plan.supplier), invoice_date
    )
    require_status(invoice, "matched")
    if plan.fate == MATCHED:
        return record

    invoice = await approve_invoice(api, invoice["id"])
    if plan.fate == APPROVED:
        return record
    if plan.fate == PAID:
        await pay_invoice(api, invoice, payment_date(invoice, ctx.today, index), f"WIRE-{invoice['id']:05d}")
    return record


def require_status(invoice: dict[str, object], expected: str) -> None:
    """The seed builds scenarios whose outcome it knows; a different one means the rules changed, so stop loudly."""
    if invoice["status"] != expected:
        raise DemoSeedError(
            f"invoice {invoice['invoice_number']} is '{invoice['status']}', expected '{expected}': "
            f"{invoice.get('exception_reasons')}"
        )


async def run_regular_orders(ctx: SeedContext, plans: tuple[OrderPlan, ...]) -> None:
    for index, plan in enumerate(plans):
        await run_plan(ctx, plan, index)
