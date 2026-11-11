"""Seed step 5: the situations a demo should show alive. Each function builds one, through the API."""

from datetime import timedelta
from decimal import Decimal

from app.demo.api import DemoSeedError
from app.demo.catalog import PRODUCTS, SUPPLIERS_BY_NAME
from app.demo.finance import (
    approve_invoice,
    invoice_lines,
    pay_invoice,
    payment_date,
    record_invoice,
    release_payment_run,
)
from app.demo.plan import PAID, LinePlan, OrderPlan, months_back
from app.demo.procure import (
    advance_order,
    approve_order,
    order_items,
    place_order,
    receipt_date,
    receive,
)
from app.demo.year import SeedContext, require_status, run_plan

PRODUCTS_BY_SKU = {product.sku: product for product in PRODUCTS}
PRICE_VARIANCE_FACTOR = Decimal("1.12")


def make_plan(
    ctx: SeedContext, supplier: str, lines: list[tuple[str, int]], months: int, day: int, fate: str, lead_days: int = 9
) -> OrderPlan:
    return OrderPlan(
        supplier=SUPPLIERS_BY_NAME[supplier],
        lines=tuple(LinePlan(PRODUCTS_BY_SKU[sku], quantity) for sku, quantity in lines),
        order_date=months_back(ctx.today, months, day),
        lead_days=lead_days,
        fate=fate,
    )


async def delegated_approval(ctx: SeedContext) -> None:
    """Priya Raman is away: Marcus Webb approves her purchase order on her behalf (a delegation set up earlier)."""
    plan = make_plan(ctx, "Prairie Office Supply Co.", [("OFF-1001", 37), ("OFF-1003", 9)], 0, 4, "ordered")
    record = await advance_order(ctx.api, ctx.foundation, plan, until="submit")
    await approve_order(ctx.api, record.po_id, first_approver="department_manager")
    await place_order(ctx.api, record.po_id)
    ctx.records.append(record)


async def amended_order(ctx: SeedContext) -> None:
    """An order raised after it was placed (approved by a manager) and then moved to a later delivery slot."""
    api, foundation = ctx.api, ctx.foundation
    plan = make_plan(ctx, "Lakeshore Packaging Inc.", [("PKG-2001", 1200), ("PKG-2002", 33)], 1, 6, PAID, lead_days=10)
    record = await advance_order(api, foundation, plan)
    ctx.records.append(record)
    bigger = tuple(
        LinePlan(line.product, line.quantity + (300 if line.product.sku == "PKG-2001" else 0)) for line in plan.lines
    )
    raised = await api.post(
        "purchasing_officer",
        f"/purchase-orders/{record.po_id}/amend",
        {
            "reason": "Forecast went up: 300 more boxes",
            "items": order_items(foundation, plan.supplier, bigger),
        },
    )
    if raised["status"] == "pending_approval":
        raised = await api.post("procurement_manager", f"/po-amendments/{raised['id']}/approve", {"comment": "Agreed"})
    await api.post(
        "purchasing_officer",
        f"/purchase-orders/{record.po_id}/amend",
        {
            "reason": "Supplier asked for a later delivery slot",
            "expected_delivery_date": str(plan.delivery_date + timedelta(days=3)),
        },
    )
    record.received_on = receipt_date(plan, ctx.today, 3)
    await receive(api, record.po_id, [(line.product, line.quantity, 0) for line in bigger], foundation, "Complete")
    invoice = await record_invoice(
        api, record, invoice_lines(bigger, foundation), ctx.numbers.next(plan.supplier), record.received_on
    )
    require_status(invoice, "matched")
    invoice = await approve_invoice(api, invoice["id"])
    await pay_invoice(api, invoice, payment_date(invoice, ctx.today, 1), f"WIRE-{invoice['id']:05d}")


async def partial_receipt_with_return(ctx: SeedContext) -> None:
    """Part of an order arrives, two units are rejected as damaged and go back to the supplier."""
    api, foundation = ctx.api, ctx.foundation
    plan = make_plan(ctx, "Brightwell Components Ltd", [("CMP-8001", 20), ("CMP-8003", 31)], 1, 12, "ordered")
    record = await advance_order(api, foundation, plan)
    ctx.records.append(record)
    record.received_on = receipt_date(plan, ctx.today, 0)
    servo, valve = (line.product for line in plan.lines)
    await receive(api, record.po_id, [(servo, 12, 2), (valve, 31, 0)], foundation, "Servo housings cracked in transit")
    returned = await api.post(
        "warehouse_manager",
        "/supplier-returns",
        {
            "po_id": record.po_id,
            "product_id": foundation.product_ids[servo.sku],
            "quantity": 2,
            "reason": "Housing cracked in transit",
            "resolution": "replace",
        },
    )
    await api.post(
        "warehouse_manager",
        f"/supplier-returns/{returned['id']}/status",
        {"status": "sent", "note": "Collected by the carrier"},
    )
    billed = (LinePlan(servo, 10), LinePlan(valve, 31))  # only what was accepted is billed
    invoice = await record_invoice(
        api, record, invoice_lines(billed, foundation), ctx.numbers.next(plan.supplier), ctx.today
    )
    require_status(invoice, "matched")


async def duplicate_invoice(ctx: SeedContext) -> None:
    """A supplier sends invoice number N twice, against two orders: the second is held as a duplicate."""
    api, foundation = ctx.api, ctx.foundation
    first_plan = make_plan(ctx, "Thames Stationery Ltd", [("STA-7001", 61)], 3, 8, PAID)
    second_plan = make_plan(ctx, "Thames Stationery Ltd", [("STA-7002", 83)], 3, 14, PAID)
    records = []
    for plan in (first_plan, second_plan):
        record = await advance_order(api, foundation, plan)
        record.received_on = receipt_date(plan, ctx.today, 0)
        await receive(
            api, record.po_id, [(line.product, line.quantity, 0) for line in plan.lines], foundation, "Complete"
        )
        ctx.records.append(record)
        records.append(record)
    number = ctx.numbers.next(first_plan.supplier)
    first = await record_invoice(
        api, records[0], invoice_lines(first_plan.lines, foundation), number, records[0].received_on or ctx.today
    )
    require_status(first, "matched")
    first = await approve_invoice(api, first["id"])
    await pay_invoice(api, first, payment_date(first, ctx.today, 2), f"WIRE-{first['id']:05d}")
    second_date = (records[1].received_on or ctx.today) + timedelta(days=1)
    second = await record_invoice(
        api, records[1], invoice_lines(second_plan.lines, foundation), number, min(second_date, ctx.today)
    )
    require_status(second, "exception")


async def price_variance_exception(ctx: SeedContext) -> None:
    """An invoice priced 12% above the order is an exception; finance approves it with a reason."""
    api, foundation = ctx.api, ctx.foundation
    plan = make_plan(ctx, "Summit Industrial Parts LLC", [("IND-3003", 210)], 2, 9, "received")
    run = await run_plan(ctx, plan, 1)
    invoice_date = (run.received_on or ctx.today) + timedelta(days=1)
    invoice = await record_invoice(
        api,
        run,
        invoice_lines(plan.lines, foundation, PRICE_VARIANCE_FACTOR),
        ctx.numbers.next(plan.supplier),
        invoice_date,
    )
    require_status(invoice, "exception")
    await approve_invoice(api, invoice["id"], "Steel surcharge agreed with the supplier")


async def large_orders(ctx: SeedContext) -> None:
    """Orders above 20,000 need two approvals: one completed last spring, one waiting for finance now."""
    done = make_plan(ctx, "Summit Industrial Parts LLC", [("IND-3001", 44)], 5, 10, PAID, lead_days=14)
    await run_plan(ctx, done, 3)
    waiting = make_plan(ctx, "Summit Industrial Parts LLC", [("IND-3001", 57), ("IND-3002", 410)], 0, 3, "pending")
    record = await advance_order(ctx.api, ctx.foundation, waiting, until="submit")
    await ctx.api.post(
        "procurement_manager", f"/purchase-orders/{record.po_id}/approve", {"comment": "Manager step done"}
    )
    ctx.records.append(record)


async def sepa_payment_run(ctx: SeedContext) -> None:
    """Two euro invoices approved by finance, paid by a SEPA payment run that a second finance user releases."""
    api = ctx.api
    invoice_ids: list[int] = []
    for supplier, sku, quantity, day in (
        ("Rheinwerk Elektronik GmbH", "ELC-4002", 66, 7),
        ("Atelier Lumiere SARL", "FAC-5002", 47, 11),
    ):
        plan = make_plan(ctx, supplier, [(sku, quantity)], 1, day, "approved")
        record = await run_plan(ctx, plan, 2)
        invoice_ids.extend(record.invoice_ids)
    run = await release_payment_run(api, invoice_ids)
    if run["status"] != "released":
        raise DemoSeedError(f"payment run {run['number']} is '{run['status']}', expected 'released'")
    ctx.sepa_run_number = run["number"]


async def seed_scenarios(ctx: SeedContext) -> None:
    for build in (
        delegated_approval,
        amended_order,
        partial_receipt_with_return,
        duplicate_invoice,
        price_variance_exception,
        large_orders,
        sepa_payment_run,
    ):
        await build(ctx)
