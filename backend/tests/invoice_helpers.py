"""Helpers that drive the HTTP API through the procure-to-pay flow: ordered and received orders, invoices, payments."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from httpx import AsyncClient, Response

from app.core.clock import utc_today
from app.models.product import Product
from app.models.supplier import Supplier
from tests.fixture_types import AuthHeaders
from tests.flow_helpers import API, draft_po

Headers = dict[str, str]
INVOICES = f"{API}/supplier-invoices"
RUNS = f"{API}/payment-runs"
RETURNS = f"{API}/supplier-returns"
POS = f"{API}/purchase-orders"
DEFAULT_QUANTITY = 10
DEFAULT_PRICE = "10.00"


@dataclass(frozen=True)
class Staff:
    """Signed-in people for the roles the flow needs."""

    officer: Headers
    manager: Headers
    finance: Headers
    finance2: Headers
    warehouse: Headers
    viewer: Headers
    admin: Headers


async def make_staff(auth_headers: AuthHeaders) -> Staff:
    return Staff(
        officer=await auth_headers("purchasing_officer"),
        manager=await auth_headers("procurement_manager"),
        finance=await auth_headers("finance"),
        finance2=await auth_headers("finance", "finance2@example.com"),
        warehouse=await auth_headers("warehouse_manager"),
        viewer=await auth_headers("viewer"),
        admin=await auth_headers("admin"),
    )


async def ordered_po(
    client: AsyncClient,
    staff: Staff,
    supplier: Supplier,
    product: Product,
    *,
    quantity: int = DEFAULT_QUANTITY,
    unit_price: str = DEFAULT_PRICE,
    **extra: Any,
) -> dict[str, Any]:
    """A purchase order that is approved and marked ordered."""
    po = await draft_po(client, staff.officer, supplier, product, quantity=quantity, unit_price=unit_price, **extra)
    submitted = await client.post(f"{POS}/{po['id']}/submit", headers=staff.officer)
    assert submitted.status_code == 200, submitted.text
    approved = await client.post(f"{POS}/{po['id']}/approve", headers=staff.manager)
    assert approved.status_code == 200, approved.text
    ordered = await client.post(f"{POS}/{po['id']}/order", headers=staff.officer)
    assert ordered.status_code == 200, ordered.text
    return dict(ordered.json())


async def receive(
    client: AsyncClient,
    staff: Staff,
    po_id: int,
    product: Product,
    quantity: int,
    rejected: int = 0,
    **extra: Any,
) -> Response:
    item = {"product_id": product.id, "quantity": quantity, "rejected_quantity": rejected, **extra}
    return await client.post(f"{POS}/{po_id}/receive", json={"items": [item]}, headers=staff.warehouse)


async def received_po(
    client: AsyncClient,
    staff: Staff,
    supplier: Supplier,
    product: Product,
    *,
    quantity: int = DEFAULT_QUANTITY,
    unit_price: str = DEFAULT_PRICE,
    **extra: Any,
) -> dict[str, Any]:
    """An ordered purchase order with everything received and accepted."""
    po = await ordered_po(client, staff, supplier, product, quantity=quantity, unit_price=unit_price, **extra)
    response = await receive(client, staff, po["id"], product, quantity)
    assert response.status_code == 200, response.text
    return dict(response.json())


def invoice_body(
    po: dict[str, Any],
    product: Product,
    *,
    number: str = "INV-1",
    quantity: int = DEFAULT_QUANTITY,
    unit_price: str = DEFAULT_PRICE,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "po_id": po["id"],
        "invoice_number": number,
        "invoice_date": utc_today().isoformat(),
        "lines": [{"product_id": product.id, "quantity": quantity, "unit_price": unit_price}],
        **extra,
    }


async def create_invoice(client: AsyncClient, headers: Headers, body: dict[str, Any]) -> dict[str, Any]:
    response = await client.post(INVOICES, json=body, headers=headers)
    assert response.status_code == 201, response.text
    return dict(response.json())


async def submit_invoice(client: AsyncClient, headers: Headers, invoice_id: int) -> Response:
    return await client.post(f"{INVOICES}/{invoice_id}/submit", headers=headers)


async def submitted_invoice(
    client: AsyncClient, staff: Staff, po: dict[str, Any], product: Product, **kwargs: Any
) -> dict[str, Any]:
    """A recorded and submitted invoice, whatever the match decided."""
    invoice = await create_invoice(client, staff.officer, invoice_body(po, product, **kwargs))
    response = await submit_invoice(client, staff.officer, invoice["id"])
    assert response.status_code == 200, response.text
    return dict(response.json())


def reason_codes(invoice: dict[str, Any]) -> list[str]:
    return [reason["code"] for reason in invoice["exception_reasons"]]


async def tax_rate(client: AsyncClient, staff: Staff, percentage: str) -> int:
    response = await client.post(
        f"{API}/tax-rates",
        json={"name": f"Tax {percentage}", "percentage": percentage, "tax_type": "vat"},
        headers=staff.finance,
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


DUPLICATE_SPACING_DAYS = 8  # one more than the duplicate window, so invoices of equal amount never look alike


async def _spread_dates(client: AsyncClient, staff: Staff, kwargs: dict[str, Any]) -> None:
    """Give each invoice its own date (unless one is given) so equal totals are not flagged as duplicates."""
    existing = (await client.get(INVOICES, params={"page_size": 1}, headers=staff.finance)).json()["total"]
    today = utc_today()
    kwargs.setdefault("invoice_date", (today - timedelta(days=DUPLICATE_SPACING_DAYS * existing)).isoformat())
    kwargs.setdefault("due_date", (today + timedelta(days=30)).isoformat())


async def matched_invoice(
    client: AsyncClient, staff: Staff, po: dict[str, Any], product: Product, **kwargs: Any
) -> dict[str, Any]:
    """A recorded and submitted invoice that matched cleanly (dated apart from the others)."""
    await _spread_dates(client, staff, kwargs)
    invoice = await create_invoice(client, staff.officer, invoice_body(po, product, **kwargs))
    response = await submit_invoice(client, staff.officer, invoice["id"])
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "matched", response.json()["exception_reasons"]
    return dict(response.json())


async def approved_invoice(
    client: AsyncClient, staff: Staff, po: dict[str, Any], product: Product, **kwargs: Any
) -> dict[str, Any]:
    """A matched invoice approved by finance."""
    invoice = await matched_invoice(client, staff, po, product, **kwargs)
    response = await client.post(f"{INVOICES}/{invoice['id']}/approve", headers=staff.finance)
    assert response.status_code == 200, response.text
    return dict(response.json())


async def get_invoice(client: AsyncClient, headers: Headers, invoice_id: int) -> dict[str, Any]:
    response = await client.get(f"{INVOICES}/{invoice_id}", headers=headers)
    assert response.status_code == 200, response.text
    return dict(response.json())


async def pay(client: AsyncClient, headers: Headers, invoice_id: int, amount: str, **extra: Any) -> Response:
    body = {"amount": amount, "method": "bank_transfer", **extra}
    return await client.post(f"{INVOICES}/{invoice_id}/payments", json=body, headers=headers)


async def add_rate(client: AsyncClient, finance: Headers, currency: str, rate: str, days_ago: int = 0) -> None:
    response = await client.post(
        f"{API}/exchange-rates",
        json={
            "currency_code": currency,
            "rate": rate,
            "effective_date": (utc_today() - timedelta(days=days_ago)).isoformat(),
        },
        headers=finance,
    )
    assert response.status_code == 201, response.text


async def set_matching(client: AsyncClient, staff: Staff, **settings: Any) -> None:
    response = await client.patch(f"{API}/company-settings", json=settings, headers=staff.admin)
    assert response.status_code == 200, response.text


async def delete_all_rates(client: AsyncClient, finance: Headers) -> None:
    rates = (await client.get(f"{API}/exchange-rates", headers=finance)).json()["items"]
    for rate in rates:
        await client.delete(f"{API}/exchange-rates/{rate['id']}", headers=finance)
