from datetime import timedelta
from decimal import Decimal
from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_today
from app.models.product import Product
from app.models.supplier import Supplier
from tests.fixture_types import AuthHeaders

PO_URL = "/api/v1/purchase-orders"


async def _tax_rate(client: AsyncClient, finance: dict[str, str], **overrides: Any) -> int:
    payload = {"name": "Test VAT 20%", "percentage": "20", "tax_type": "vat", **overrides}
    response = await client.post("/api/v1/tax-rates", json=payload, headers=finance)
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


async def _create_po(
    client: AsyncClient, headers: dict[str, str], supplier: Supplier, lines: list[dict[str, Any]], **extra: Any
) -> Any:
    return await client.post(PO_URL, json={"supplier_id": supplier.id, "items": lines, **extra}, headers=headers)


def _line(product: Product, quantity: int, unit_price: str, tax_rate_id: int | None = None) -> dict[str, Any]:
    return {"product_id": product.id, "quantity": quantity, "unit_price": unit_price, "tax_rate_id": tax_rate_id}


async def _second_product(db_session: AsyncSession, supplier: Supplier) -> Product:
    other = Product(sku="TEST-002", name="Second Widget", cost=5, minimum_stock=1, supplier_id=supplier.id)
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)
    return other


async def _approved_po(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product, **extra: Any
) -> dict[str, Any]:
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    created = await _create_po(client, officer, supplier, [_line(product, 10, "10.00")], **extra)
    po_id = created.json()["id"]
    await client.post(f"{PO_URL}/{po_id}/submit", headers=officer)
    response = await client.post(f"{PO_URL}/{po_id}/approve", headers=manager)
    assert response.status_code == 200, response.text
    return dict(response.json())


async def test_exclusive_tax_is_added_to_the_line(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    finance = await auth_headers("finance")
    officer = await auth_headers("purchasing_officer")
    tax_id = await _tax_rate(client, finance)

    response = await _create_po(client, officer, supplier, [_line(product, 3, "19.99", tax_id)])

    assert response.status_code == 201
    body = response.json()
    assert body["currency_code"] == "USD"
    assert (body["subtotal"], body["tax_total"], body["grand_total"], body["total"]) == (
        "59.97",
        "11.99",
        "71.96",
        "71.96",
    )
    [item] = body["items"]
    assert (item["line_net"], item["line_tax"], item["line_total"]) == ("59.97", "11.99", "71.96")
    assert item["tax_name"] == "Test VAT 20%"
    assert Decimal(item["tax_percent"]) == 20
    assert body["exchange_rate"] is None
    assert body["base_grand_total"] is None


async def test_inclusive_tax_is_taken_out_of_the_price(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    finance = await auth_headers("finance")
    officer = await auth_headers("purchasing_officer")
    tax_id = await _tax_rate(client, finance, name="DE VAT incl.", percentage="19", is_inclusive=True)

    response = await _create_po(client, officer, supplier, [_line(product, 1, "119.00", tax_id)])

    body = response.json()
    assert (body["subtotal"], body["tax_total"], body["grand_total"]) == ("100.00", "19.00", "119.00")


async def test_each_line_is_rounded_before_the_totals_are_added(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    db_session: AsyncSession,
    supplier: Supplier,
    product: Product,
) -> None:
    officer = await auth_headers("purchasing_officer")
    other = await _second_product(db_session, supplier)

    response = await _create_po(client, officer, supplier, [_line(product, 1, "1.6665"), _line(other, 1, "1.6665")])

    # 1.6665 rounds half-up to 1.67 per line; rounding the 3.333 sum instead would give 3.33.
    assert response.json()["subtotal"] == "3.34"


async def test_a_line_without_a_tax_rate_has_no_tax(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    officer = await auth_headers("purchasing_officer")

    body = (await _create_po(client, officer, supplier, [_line(product, 2, "5.50")])).json()

    assert (body["subtotal"], body["tax_total"], body["grand_total"]) == ("11.00", "0.00", "11.00")
    assert body["items"][0]["tax_rate_id"] is None
    assert body["items"][0]["tax_name"] is None


async def test_unknown_and_inactive_tax_rates_are_refused(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    finance = await auth_headers("finance")
    officer = await auth_headers("purchasing_officer")
    retired_id = await _tax_rate(client, finance)
    await client.patch(f"/api/v1/tax-rates/{retired_id}", json={"is_active": False}, headers=finance)

    unknown = await _create_po(client, officer, supplier, [_line(product, 1, "5.00", 9999)])
    retired = await _create_po(client, officer, supplier, [_line(product, 1, "5.00", retired_id)])

    assert unknown.status_code == 400
    assert retired.status_code == 400


async def test_editing_a_tax_rate_never_changes_an_existing_order(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    finance = await auth_headers("finance")
    officer = await auth_headers("purchasing_officer")
    tax_id = await _tax_rate(client, finance)
    po_id = (await _create_po(client, officer, supplier, [_line(product, 10, "10.00", tax_id)])).json()["id"]

    await client.patch(f"/api/v1/tax-rates/{tax_id}", json={"percentage": "25", "name": "Renamed"}, headers=finance)
    saved = await client.patch(f"{PO_URL}/{po_id}", json={"notes": "touch"}, headers=officer)
    current = (await client.get(f"{PO_URL}/{po_id}", headers=officer)).json()

    assert saved.status_code == 200
    assert current["grand_total"] == "120.00"
    assert current["items"][0]["tax_name"] == "Test VAT 20%"
    assert Decimal(current["items"][0]["tax_percent"]) == 20


async def test_a_new_order_uses_the_supplier_default_currency(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    manager = await auth_headers("procurement_manager")
    await client.patch(f"/api/v1/suppliers/{supplier.id}", json={"currency_code": "EUR"}, headers=manager)
    officer = await auth_headers("purchasing_officer")

    default = await _create_po(client, officer, supplier, [_line(product, 1, "5.00")])
    explicit = await _create_po(client, officer, supplier, [_line(product, 1, "5.00")], currency_code="gbp")

    assert default.json()["currency_code"] == "EUR"
    assert explicit.json()["currency_code"] == "GBP"


async def test_an_inactive_or_unknown_currency_is_refused(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    officer = await auth_headers("purchasing_officer")

    inactive = await _create_po(client, officer, supplier, [_line(product, 1, "5.00")], currency_code="JPY")
    unknown = await _create_po(client, officer, supplier, [_line(product, 1, "5.00")], currency_code="ZZZ")

    assert inactive.status_code == 400
    assert unknown.status_code == 400


async def test_changing_a_draft_currency_reprices_it_in_the_new_minor_units(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    finance = await auth_headers("finance")
    officer = await auth_headers("purchasing_officer")
    await client.patch("/api/v1/currencies/JPY", json={"is_active": True}, headers=finance)
    po_id = (await _create_po(client, officer, supplier, [_line(product, 3, "333.5")])).json()["id"]

    response = await client.patch(f"{PO_URL}/{po_id}", json={"currency_code": "JPY"}, headers=officer)

    body = response.json()
    assert response.status_code == 200
    assert body["currency_code"] == "JPY"
    # 3 x 333.5 = 1000.5 rounds half-up to a whole yen; the amount is shown with two display decimals.
    assert Decimal(body["grand_total"]) == Decimal(1001)


async def test_an_order_in_a_foreign_currency_cannot_be_submitted_without_a_rate(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    officer = await auth_headers("purchasing_officer")
    po_id = (await _create_po(client, officer, supplier, [_line(product, 10, "10.00")], currency_code="EUR")).json()[
        "id"
    ]

    response = await client.post(f"{PO_URL}/{po_id}/submit", headers=officer)

    # Approval rules and limits are written in the base currency, so the amount must be convertible up front.
    assert response.status_code == 409
    assert "exchange rate" in response.json()["detail"]
    assert (await client.get(f"{PO_URL}/{po_id}", headers=officer)).json()["status"] == "draft"


async def test_a_rate_that_disappears_after_submission_blocks_approval_and_leaves_the_order_submitted(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    finance = await auth_headers("finance")
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    rate_id = (
        await client.post(
            "/api/v1/exchange-rates",
            json={"currency_code": "EUR", "rate": "1.1", "effective_date": utc_today().isoformat()},
            headers=finance,
        )
    ).json()["id"]
    po_id = (await _create_po(client, officer, supplier, [_line(product, 10, "10.00")], currency_code="EUR")).json()[
        "id"
    ]
    await client.post(f"{PO_URL}/{po_id}/submit", headers=officer)
    await client.delete(f"/api/v1/exchange-rates/{rate_id}", headers=finance)

    response = await client.post(f"{PO_URL}/{po_id}/approve", headers=manager)

    assert response.status_code == 409
    assert "exchange rate" in response.json()["detail"]
    current = (await client.get(f"{PO_URL}/{po_id}", headers=manager)).json()
    assert current["status"] == "submitted"
    assert current["exchange_rate"] is None


async def test_approval_locks_the_rate_and_later_rates_never_move_it(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    finance = await auth_headers("finance")
    today = utc_today()
    await client.post(
        "/api/v1/exchange-rates",
        json={"currency_code": "EUR", "rate": "1.1", "effective_date": (today - timedelta(days=3)).isoformat()},
        headers=finance,
    )

    approved = await _approved_po(client, auth_headers, supplier, product, currency_code="EUR")
    await client.post(
        "/api/v1/exchange-rates",
        json={"currency_code": "EUR", "rate": "1.5", "effective_date": today.isoformat()},
        headers=finance,
    )
    viewer = await auth_headers("viewer")
    again = (await client.get(f"{PO_URL}/{approved['id']}", headers=viewer)).json()

    assert approved["status"] == "approved"
    assert Decimal(approved["exchange_rate"]) == Decimal("1.1")
    assert approved["grand_total"] == "100.00"
    assert approved["base_grand_total"] == "110.00"
    assert Decimal(again["exchange_rate"]) == Decimal("1.1")
    assert again["base_grand_total"] == "110.00"


async def test_the_latest_rate_on_or_before_approval_day_is_used(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    finance = await auth_headers("finance")
    today = utc_today()
    for days_ago, rate in ((30, "1.00"), (5, "1.20"), (-5, "9.99")):
        await client.post(
            "/api/v1/exchange-rates",
            json={
                "currency_code": "EUR",
                "rate": rate,
                "effective_date": (today - timedelta(days=days_ago)).isoformat(),
            },
            headers=finance,
        )

    approved = await _approved_po(client, auth_headers, supplier, product, currency_code="EUR")

    assert Decimal(approved["exchange_rate"]) == Decimal("1.2")
    assert approved["base_grand_total"] == "120.00"


async def test_base_currency_orders_lock_at_rate_one(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    approved = await _approved_po(client, auth_headers, supplier, product)

    assert Decimal(approved["exchange_rate"]) == 1
    assert approved["base_subtotal"] == "100.00"
    assert approved["base_grand_total"] == "100.00"


async def test_base_amounts_are_converted_per_total_and_still_add_up(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    finance = await auth_headers("finance")
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    tax_id = await _tax_rate(client, finance)
    await client.post(
        "/api/v1/exchange-rates",
        json={"currency_code": "EUR", "rate": "1.08345678", "effective_date": utc_today().isoformat()},
        headers=finance,
    )
    po_id = (
        await _create_po(client, officer, supplier, [_line(product, 7, "13.37", tax_id)], currency_code="EUR")
    ).json()["id"]
    await client.post(f"{PO_URL}/{po_id}/submit", headers=officer)

    body = (await client.post(f"{PO_URL}/{po_id}/approve", headers=manager)).json()

    assert Decimal(body["base_subtotal"]) + Decimal(body["base_tax_total"]) == Decimal(body["base_grand_total"])
    assert body["base_subtotal"] == "101.40"


async def test_the_base_currency_can_change_until_an_order_is_approved(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    admin = await auth_headers("admin")

    before = await client.patch("/api/v1/company-settings", json={"base_currency_code": "EUR"}, headers=admin)
    await client.patch("/api/v1/company-settings", json={"base_currency_code": "USD"}, headers=admin)
    await _approved_po(client, auth_headers, supplier, product)
    after = await client.patch("/api/v1/company-settings", json={"base_currency_code": "EUR"}, headers=admin)
    same = await client.patch("/api/v1/company-settings", json={"base_currency_code": "USD"}, headers=admin)

    assert before.status_code == 200
    assert after.status_code == 409
    assert same.status_code == 200


async def test_an_inactive_or_unknown_base_currency_is_refused(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    admin = await auth_headers("admin")

    inactive = await client.patch("/api/v1/company-settings", json={"base_currency_code": "JPY"}, headers=admin)
    unknown = await client.patch("/api/v1/company-settings", json={"base_currency_code": "ZZZ"}, headers=admin)

    assert inactive.status_code == 400
    assert unknown.status_code == 400


async def test_supplier_payment_fields_are_validated(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier
) -> None:
    manager = await auth_headers("procurement_manager")
    url = f"/api/v1/suppliers/{supplier.id}"

    ok = await client.patch(
        url,
        json={"country_code": "de", "tax_id": "DE123456789", "currency_code": "eur", "payment_terms_days": 45},
        headers=manager,
    )
    bad_country = await client.patch(url, json={"country_code": "DEU"}, headers=manager)
    bad_terms = await client.patch(url, json={"payment_terms_days": -1}, headers=manager)
    unknown_currency = await client.patch(url, json={"currency_code": "ZZZ"}, headers=manager)

    assert ok.status_code == 200
    assert ok.json()["country_code"] == "DE"
    assert ok.json()["currency_code"] == "EUR"
    assert ok.json()["payment_terms_days"] == 45
    assert bad_country.status_code == 422
    assert bad_terms.status_code == 422
    assert unknown_currency.status_code == 400
