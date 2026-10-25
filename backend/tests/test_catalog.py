from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_today
from app.models.product import Product
from app.models.supplier import Supplier
from tests.fixture_types import AuthHeaders
from tests.flow_helpers import API

CATALOG_URL = f"{API}/catalog-items"


async def _add(
    client: AsyncClient, headers: dict[str, str], supplier: Supplier, product: Product, **overrides: Any
) -> Response:
    payload: dict[str, Any] = {
        "product_id": product.id,
        "supplier_id": supplier.id,
        "contract_price": "8.5000",
        "lead_time_days": 7,
        **overrides,
    }
    return await client.post(CATALOG_URL, json=payload, headers=headers)


async def test_the_catalog_requires_sign_in(client: AsyncClient) -> None:
    assert (await client.get(CATALOG_URL)).status_code == 401
    assert (await client.post(CATALOG_URL, json={})).status_code == 401


async def test_a_procurement_manager_adds_an_item_and_anyone_can_read_it(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    manager = await auth_headers("procurement_manager")
    employee = await auth_headers("employee")

    created = await _add(client, manager, supplier, product)
    listed = await client.get(CATALOG_URL, headers=employee)

    assert created.status_code == 201
    body = created.json()
    assert (body["product_sku"], body["product_name"], body["supplier_name"]) == (
        "TEST-001",
        "Test Widget",
        "Test Supplier",
    )
    assert (body["contract_price"], body["currency_code"], body["lead_time_days"]) == ("8.50", "USD", 7)
    assert body["is_current"] is True
    assert [row["id"] for row in listed.json()] == [body["id"]]


@pytest.mark.parametrize("role", ["viewer", "employee", "purchasing_officer", "finance", "department_manager"])
async def test_only_catalog_managers_can_change_it(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product, role: str
) -> None:
    manager = await auth_headers("procurement_manager")
    item_id = (await _add(client, manager, supplier, product)).json()["id"]
    headers = await auth_headers(role)

    create = await _add(client, headers, supplier, product, contract_price="1")
    update = await client.patch(f"{CATALOG_URL}/{item_id}", json={"contract_price": "1"}, headers=headers)

    assert create.status_code == 403
    assert update.status_code == 403


async def test_the_currency_defaults_to_the_suppliers_then_the_base_currency(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    manager = await auth_headers("procurement_manager")
    await client.patch(f"{API}/suppliers/{supplier.id}", json={"currency_code": "EUR"}, headers=manager)

    default = await _add(client, manager, supplier, product)
    explicit = await _add(client, manager, supplier, product, currency_code="gbp")

    assert default.json()["currency_code"] == "EUR"
    assert explicit.json()["currency_code"] == "GBP"


async def test_one_entry_per_product_supplier_and_currency(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    manager = await auth_headers("procurement_manager")
    await _add(client, manager, supplier, product)

    duplicate = await _add(client, manager, supplier, product)
    other_currency = await _add(client, manager, supplier, product, currency_code="EUR")

    assert duplicate.status_code == 409
    assert other_currency.status_code == 201


@pytest.mark.parametrize(
    "overrides",
    [
        {"contract_price": "-1"},
        {"contract_price": "1.23456"},
        {"lead_time_days": -1},
        {"lead_time_days": 4000},
        {"valid_from": "2026-06-01", "valid_until": "2026-05-01"},
        {"product_id": 99999},
        {"supplier_id": 99999},
        {"currency_code": "JPY"},
    ],
)
async def test_invalid_items_are_rejected(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product, overrides: dict[str, Any]
) -> None:
    manager = await auth_headers("procurement_manager")

    response = await _add(client, manager, supplier, product, **overrides)

    assert response.status_code in {400, 422}


async def test_whether_a_contract_is_current_is_worked_out_from_todays_date(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession, supplier: Supplier, product: Product
) -> None:
    manager = await auth_headers("procurement_manager")
    today = utc_today()
    other = Product(sku="TEST-002", name="Second Widget", cost=5, minimum_stock=1, supplier_id=supplier.id)
    third = Product(sku="TEST-003", name="Third Widget", cost=5, minimum_stock=1, supplier_id=supplier.id)
    fourth = Product(sku="TEST-004", name="Fourth Widget", cost=5, minimum_stock=1, supplier_id=supplier.id)
    db_session.add_all([other, third, fourth])
    await db_session.commit()

    open_ended = await _add(client, manager, supplier, product)
    future = await _add(client, manager, supplier, other, valid_from=(today + timedelta(days=3)).isoformat())
    expired = await _add(client, manager, supplier, third, valid_until=(today - timedelta(days=1)).isoformat())
    last_day = await _add(client, manager, supplier, fourth, valid_until=today.isoformat())

    assert open_ended.json()["is_current"] is True
    assert future.json()["is_current"] is False
    assert expired.json()["is_current"] is False
    assert last_day.json()["is_current"] is True


async def test_an_item_can_be_repriced_and_switched_off(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    manager = await auth_headers("procurement_manager")
    item_id = (await _add(client, manager, supplier, product)).json()["id"]

    repriced = await client.patch(
        f"{CATALOG_URL}/{item_id}", json={"contract_price": "7.25", "lead_time_days": 3}, headers=manager
    )
    switched_off = await client.patch(f"{CATALOG_URL}/{item_id}", json={"is_active": False}, headers=manager)
    active_only = await client.get(CATALOG_URL, params={"active_only": True}, headers=manager)

    assert (repriced.json()["contract_price"], repriced.json()["lead_time_days"]) == ("7.25", 3)
    assert switched_off.json()["is_active"] is False
    assert switched_off.json()["is_current"] is False
    assert active_only.json() == []


async def test_edits_cannot_empty_required_fields_or_reverse_the_dates(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    manager = await auth_headers("procurement_manager")
    item_id = (
        await _add(client, manager, supplier, product, valid_from="2026-01-01", valid_until="2026-12-31")
    ).json()["id"]

    cleared = await client.patch(f"{CATALOG_URL}/{item_id}", json={"contract_price": None}, headers=manager)
    reversed_dates = await client.patch(f"{CATALOG_URL}/{item_id}", json={"valid_until": "2025-01-01"}, headers=manager)
    unknown = await client.patch(f"{CATALOG_URL}/99999", json={"is_active": False}, headers=manager)

    assert cleared.status_code == 422
    assert reversed_dates.status_code == 422
    assert unknown.status_code == 404


async def test_the_list_can_be_filtered_and_searched(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession, supplier: Supplier, product: Product
) -> None:
    manager = await auth_headers("procurement_manager")
    other_supplier = Supplier(name="Northwind Traders", email="n@example.com")
    other_product = Product(sku="PEN-9", name="Gel Pen", cost=1, minimum_stock=1, supplier_id=supplier.id)
    db_session.add_all([other_supplier, other_product])
    await db_session.commit()
    widget = (await _add(client, manager, supplier, product)).json()["id"]
    pen = (await _add(client, manager, other_supplier, other_product)).json()["id"]

    by_supplier = await client.get(CATALOG_URL, params={"supplier_id": other_supplier.id}, headers=manager)
    by_product = await client.get(CATALOG_URL, params={"product_id": product.id}, headers=manager)
    by_text = await client.get(CATALOG_URL, params={"search": "gel"}, headers=manager)
    by_sku = await client.get(CATALOG_URL, params={"search": "test-001"}, headers=manager)
    by_supplier_name = await client.get(CATALOG_URL, params={"search": "northwind"}, headers=manager)

    assert [row["id"] for row in by_supplier.json()] == [pen]
    assert [row["id"] for row in by_product.json()] == [widget]
    assert [row["id"] for row in by_text.json()] == [pen]
    assert [row["id"] for row in by_sku.json()] == [widget]
    assert [row["id"] for row in by_supplier_name.json()] == [pen]


async def test_a_request_line_can_start_from_a_catalog_item(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    manager = await auth_headers("procurement_manager")
    employee = await auth_headers("employee")
    item = (await _add(client, manager, supplier, product)).json()

    response = await client.post(
        f"{API}/purchase-requests",
        json={
            "title": "Widgets",
            "lines": [{"description": "Test Widget", "quantity": 4, "catalog_item_id": item["id"]}],
        },
        headers=employee,
    )

    assert response.status_code == 201
    [line] = response.json()["lines"]
    assert (line["product_id"], line["supplier_id"], line["catalog_item_id"]) == (product.id, supplier.id, item["id"])
    assert (line["estimated_unit_price"], line["line_total"]) == ("8.50", "34.00")


async def test_a_request_line_cannot_use_an_expired_or_foreign_currency_item(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession, supplier: Supplier, product: Product
) -> None:
    manager = await auth_headers("procurement_manager")
    employee = await auth_headers("employee")
    other = Product(sku="TEST-002", name="Second Widget", cost=5, minimum_stock=1, supplier_id=supplier.id)
    db_session.add(other)
    await db_session.commit()
    expired = (
        await _add(client, manager, supplier, product, valid_until=(utc_today() - timedelta(days=1)).isoformat())
    ).json()
    in_euros = (await _add(client, manager, supplier, other, currency_code="EUR")).json()

    def request_with(item_id: int) -> dict[str, Any]:
        return {"title": "x", "lines": [{"description": "x", "quantity": 1, "catalog_item_id": item_id}]}

    expired_response = await client.post(f"{API}/purchase-requests", json=request_with(expired["id"]), headers=employee)
    euro_response = await client.post(f"{API}/purchase-requests", json=request_with(in_euros["id"]), headers=employee)
    unknown_response = await client.post(f"{API}/purchase-requests", json=request_with(99999), headers=employee)

    assert expired_response.status_code == 400
    assert euro_response.status_code == 422
    assert "priced in EUR" in euro_response.json()["detail"]
    assert unknown_response.status_code == 400
