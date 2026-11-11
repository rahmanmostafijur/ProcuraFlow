"""Seed step 3: paying for what was ordered. Supplier invoices, matching, approval, payments, payment runs."""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.demo.api import DemoApi
from app.demo.catalog import SupplierSpec
from app.demo.plan import LinePlan
from app.demo.procure import OrderRecord
from app.demo.setup import Foundation

FIRST_INVOICE_NUMBER = 26_000
INVOICE_NUMBER_STEP = 13
PAYMENT_LEAD_DAYS = (0, 2, 4, 1, 3)
PRICE_STEP = Decimal("0.0001")
CENT = Decimal("0.01")


class InvoiceNumbers:
    """Invoice numbers a supplier would print: a prefix and a running number, never repeated for one supplier."""

    def __init__(self) -> None:
        self._issued: dict[str, int] = {}

    def next(self, supplier: SupplierSpec) -> str:
        count = self._issued.get(supplier.name, 0)
        self._issued[supplier.name] = count + 1
        return f"{supplier.short}-{FIRST_INVOICE_NUMBER + count * INVOICE_NUMBER_STEP}"


def invoice_lines(
    lines: tuple[LinePlan, ...], foundation: Foundation, price_factor: Decimal = Decimal(1)
) -> list[dict[str, Any]]:
    """Invoice lines for what was ordered; ``price_factor`` bills above or below the order price."""
    return [
        {
            "product_id": foundation.product_ids[line.product.sku],
            "quantity": line.quantity,
            "unit_price": str((line.product.price * price_factor).quantize(PRICE_STEP, rounding=ROUND_HALF_UP)),
        }
        for line in lines
    ]


async def record_invoice(
    api: DemoApi,
    record: OrderRecord,
    lines: list[dict[str, Any]],
    number: str,
    invoice_date: date,
    notes: str | None = None,
) -> dict[str, Any]:
    """The invoice as the purchasing officer enters it, submitted so it is matched against the order."""
    created = await api.post(
        "purchasing_officer",
        "/supplier-invoices",
        {
            "po_id": record.po_id,
            "invoice_number": number,
            "invoice_date": str(invoice_date),
            "notes": notes,
            "lines": lines,
        },
    )
    submitted = await api.post("purchasing_officer", f"/supplier-invoices/{created['id']}/submit")
    record.invoice_ids = (*record.invoice_ids, created["id"])
    return submitted  # type: ignore[no-any-return]


async def approve_invoice(api: DemoApi, invoice_id: int, comment: str | None = None) -> dict[str, Any]:
    body = {"comment": comment} if comment else None
    return await api.post("finance", f"/supplier-invoices/{invoice_id}/approve", body)  # type: ignore[no-any-return]


def payment_date(invoice: dict[str, Any], today: date, index: int) -> date:
    """Paid a few days before it was due, never before it was dated and never in the future."""
    due = date.fromisoformat(invoice["due_date"])
    earliest = date.fromisoformat(invoice["invoice_date"])
    return min(today, max(earliest, due - timedelta(days=PAYMENT_LEAD_DAYS[index % len(PAYMENT_LEAD_DAYS)])))


async def pay_invoice(
    api: DemoApi, invoice: dict[str, Any], paid_on: date, reference: str, share_percent: int = 100
) -> dict[str, Any]:
    """Pay the invoice's open amount, or part of it (``share_percent``), by bank transfer."""
    amount = (Decimal(invoice["open_amount"]) * share_percent / 100).quantize(CENT, rounding=ROUND_HALF_UP)
    return await api.post(  # type: ignore[no-any-return]
        "finance",
        f"/supplier-invoices/{invoice['id']}/payments",
        {"amount": str(amount), "method": "bank_transfer", "paid_on": str(paid_on), "reference": reference},
    )


async def release_payment_run(api: DemoApi, invoice_ids: list[int]) -> dict[str, Any]:
    """One finance user creates the run, a second one releases it (the rule for every payment run)."""
    run = await api.post("finance", "/payment-runs", {"invoice_ids": invoice_ids})
    return await api.post("finance_approver", f"/payment-runs/{run['id']}/release")  # type: ignore[no-any-return]
