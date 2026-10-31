"""Helpers for the payment file tests: company payer details, supplier bank details and released payment runs."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.supplier import Supplier
from tests.flow_helpers import API
from tests.invoice_helpers import RUNS, Staff, add_rate, approved_invoice, received_po

GERMAN_IBAN = "DE89370400440532013000"
FRENCH_IBAN = "FR1420041010050500013M02606"
BRAZIL_IBAN = "BR1800360305000010009795493C1"
CHASE_ROUTING = "021000021"
BOA_ROUTING = "026009593"
OUR_IBAN = "NL91ABNA0417164300"
OUR_ROUTING = "011000015"  # Federal Reserve Bank of Atlanta, a published ABA number


async def set_payer(client: AsyncClient, staff: Staff, **overrides: Any) -> None:
    body = {
        "payer_iban": OUR_IBAN,
        "payer_bic": "ABNANL2A",
        "payer_routing_number": OUR_ROUTING,
        "payer_account_number": "1234567890",
        "ach_company_id": "1234567890",
    } | overrides
    response = await client.patch(f"{API}/company-settings", json=body, headers=staff.admin)
    assert response.status_code == 200, response.text


def sepa_details(iban: str = GERMAN_IBAN, country: str = "DE", name: str = "Test Supplier GmbH") -> dict[str, Any]:
    return {"bank_account_name": name, "bank_country": country, "iban": iban, "bic": "COBADEFFXXX"}


def ach_details(
    routing: str = CHASE_ROUTING, account: str = "000123456789", name: str = "Test Supplier Inc"
) -> dict[str, Any]:
    return {"bank_account_name": name, "bank_country": "US", "bank_account_number": account, "routing_number": routing}


async def set_bank_details(client: AsyncClient, staff: Staff, supplier_id: int, body: dict[str, Any]) -> None:
    """Requested by one finance user and approved by the other, as the rules require."""
    base = f"{API}/suppliers/{supplier_id}/bank-details/changes"
    created = await client.post(base, json=body, headers=staff.finance)
    assert created.status_code == 201, created.text
    approved = await client.post(f"{base}/{created.json()['id']}/approve", json={}, headers=staff.finance2)
    assert approved.status_code == 200, approved.text


async def second_supplier(db: AsyncSession, name: str = "Second Supplier") -> tuple[Supplier, Product]:
    supplier = Supplier(name=name, email="second@example.com")
    db.add(supplier)
    await db.flush()
    product = Product(sku=f"SKU-{supplier.id}", name="Second Widget", cost=10, minimum_stock=0, supplier_id=supplier.id)
    db.add(product)
    await db.commit()
    await db.refresh(supplier)
    await db.refresh(product)
    return supplier, product


async def approved_invoice_for(
    client: AsyncClient,
    staff: Staff,
    supplier: Supplier,
    product: Product,
    number: str,
    currency: str = "USD",
    **po: Any,
) -> dict[str, Any]:
    if currency != "USD":
        known = (await client.get(f"{API}/exchange-rates", headers=staff.finance)).json()["items"]
        if not any(rate["currency_code"] == currency for rate in known):
            await add_rate(client, staff.finance, currency, "1.1")
        po = {"currency_code": currency} | po
    order = await received_po(client, staff, supplier, product, **po)
    return await approved_invoice(client, staff, order, product, number=number)


async def draft_run(client: AsyncClient, staff: Staff, invoice_ids: list[int]) -> dict[str, Any]:
    response = await client.post(RUNS, json={"invoice_ids": invoice_ids}, headers=staff.finance)
    assert response.status_code == 201, response.text
    return dict(response.json())


async def released_run(client: AsyncClient, staff: Staff, invoice_ids: list[int]) -> dict[str, Any]:
    run = await draft_run(client, staff, invoice_ids)
    released = await client.post(f"{RUNS}/{run['id']}/release", headers=staff.finance2)
    assert released.status_code == 200, released.text
    return dict(released.json())
