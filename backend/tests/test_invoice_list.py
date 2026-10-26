from datetime import timedelta
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.core.clock import utc_today
from app.models.product import Product
from app.models.supplier import Supplier
from tests.invoice_helpers import (
    INVOICES,
    Staff,
    approved_invoice,
    create_invoice,
    invoice_body,
    received_po,
    submit_invoice,
)


async def _list(client: AsyncClient, staff: Staff, **params: Any) -> dict[str, Any]:
    response = await client.get(INVOICES, params=params, headers=staff.finance)
    assert response.status_code == 200, response.text
    return dict(response.json())


async def _numbers(client: AsyncClient, staff: Staff, **params: Any) -> list[str]:
    return [row["invoice_number"] for row in (await _list(client, staff, **params))["items"]]


@pytest_asyncio.fixture
async def three_invoices(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> dict[str, dict[str, Any]]:
    """A draft, a matched invoice and an approved one, on three separate orders."""
    result: dict[str, dict[str, Any]] = {}
    for name in ("draft", "matched", "approved"):
        po = await received_po(client, staff, supplier, product)
        number = f"INV-{name.upper()}"
        if name == "approved":
            result[name] = await approved_invoice(client, staff, po, product, number=number)
            continue
        # Far apart in time, so equal totals are not taken for duplicates.
        date = (utc_today() - timedelta(days=40 if name == "draft" else 24)).isoformat()
        invoice = await create_invoice(
            client, staff.officer, invoice_body(po, product, number=number, invoice_date=date)
        )
        if name == "matched":
            await submit_invoice(client, staff.officer, invoice["id"])
        result[name] = invoice
    return result


async def test_the_list_is_newest_first_with_paging_details(
    client: AsyncClient, staff: Staff, three_invoices: dict[str, dict[str, Any]]
) -> None:
    body = await _list(client, staff, page_size=2)

    assert [row["invoice_number"] for row in body["items"]] == ["INV-APPROVED", "INV-MATCHED"]
    assert (body["total"], body["page"], body["page_size"], body["total_pages"]) == (3, 1, 2, 2)
    second = await _list(client, staff, page_size=2, page=2)
    assert [row["invoice_number"] for row in second["items"]] == ["INV-DRAFT"]


async def test_the_list_can_be_filtered_by_status(
    client: AsyncClient, staff: Staff, three_invoices: dict[str, dict[str, Any]]
) -> None:
    assert await _numbers(client, staff, status="approved") == ["INV-APPROVED"]
    assert await _numbers(client, staff, status="draft") == ["INV-DRAFT"]
    assert await _numbers(client, staff, status="void") == []


async def test_the_list_can_be_filtered_by_supplier_and_by_order(
    client: AsyncClient,
    staff: Staff,
    supplier: Supplier,
    three_invoices: dict[str, dict[str, Any]],
) -> None:
    matched = three_invoices["matched"]

    assert len(await _numbers(client, staff, supplier_id=supplier.id)) == 3
    assert await _numbers(client, staff, supplier_id=supplier.id + 1000) == []
    assert await _numbers(client, staff, po_id=matched["purchase_order"]["id"]) == ["INV-MATCHED"]


async def test_the_due_before_filter_is_strictly_before_the_day(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    today = utc_today()
    for number, offset in (("DUE-PAST", -2), ("DUE-TODAY", 0), ("DUE-LATER", 3)):
        po = await received_po(client, staff, supplier, product)
        await create_invoice(
            client,
            staff.officer,
            invoice_body(
                po,
                product,
                number=number,
                invoice_date=(today - timedelta(days=5)).isoformat(),
                due_date=(today + timedelta(days=offset)).isoformat(),
            ),
        )

    before_today = await _numbers(client, staff, due_before=today.isoformat())
    before_tomorrow = await _numbers(client, staff, due_before=(today + timedelta(days=1)).isoformat())

    assert before_today == ["DUE-PAST"]
    assert before_tomorrow == ["DUE-TODAY", "DUE-PAST"]


async def test_the_search_matches_part_of_the_invoice_number_in_any_case(
    client: AsyncClient, staff: Staff, three_invoices: dict[str, dict[str, Any]]
) -> None:
    assert await _numbers(client, staff, search="matc") == ["INV-MATCHED"]
    assert await _numbers(client, staff, search="inv-") == ["INV-APPROVED", "INV-MATCHED", "INV-DRAFT"]
    assert await _numbers(client, staff, search="nothing") == []


@pytest.mark.parametrize("search", ["%", "_", "\\", "INV_DRAFT", "%DRAFT"])
async def test_search_characters_are_taken_literally(
    client: AsyncClient, staff: Staff, three_invoices: dict[str, dict[str, Any]], search: str
) -> None:
    assert await _numbers(client, staff, search=search) == []


async def test_filters_combine(
    client: AsyncClient, staff: Staff, supplier: Supplier, three_invoices: dict[str, dict[str, Any]]
) -> None:
    assert await _numbers(client, staff, status="matched", search="INV", supplier_id=supplier.id) == ["INV-MATCHED"]
    assert await _numbers(client, staff, status="matched", search="DRAFT") == []


async def test_the_totals_describe_everything_the_filters_match_not_just_the_page(
    client: AsyncClient, staff: Staff, three_invoices: dict[str, dict[str, Any]]
) -> None:
    body = await _list(client, staff, page_size=1)

    assert len(body["items"]) == 1
    assert body["totals"]["by_status"] == {
        "draft": 1,
        "matched": 1,
        "exception": 0,
        "approved": 1,
        "on_hold": 0,
        "paid": 0,
        "void": 0,
    }
    assert body["totals"]["needing_attention"] == 1
    assert body["totals"]["payables_outstanding"] == "100.00"
    assert body["totals"]["payables_overdue"] == "0.00"


async def test_an_invalid_filter_value_or_page_size_is_refused(client: AsyncClient, staff: Staff) -> None:
    assert (await client.get(INVOICES, params={"status": "lost"}, headers=staff.finance)).status_code == 422
    assert (await client.get(INVOICES, params={"page_size": 101}, headers=staff.finance)).status_code == 422
    assert (await client.get(INVOICES, params={"page": 0}, headers=staff.finance)).status_code == 422
    assert (await client.get(INVOICES, params={"due_before": "tomorrow"}, headers=staff.finance)).status_code == 422
    assert (await client.get(INVOICES, params={"search": "x" * 101}, headers=staff.finance)).status_code == 422


async def test_an_invoice_is_readable_by_id_with_its_lines_and_reasons(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    invoice = await create_invoice(client, staff.officer, invoice_body(po, product, unit_price="30.00"))
    await submit_invoice(client, staff.officer, invoice["id"])

    response = await client.get(f"{INVOICES}/{invoice['id']}", headers=staff.manager)

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "exception"
    assert len(body["lines"]) == 1
    assert {reason["code"] for reason in body["exception_reasons"]} == {"PRICE_VARIANCE", "TOTAL_EXCEEDS_ORDER"}
    assert (await client.get(f"{INVOICES}/99999", headers=staff.manager)).status_code == 404
