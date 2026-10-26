from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_today
from app.models.audit import AuditLog
from app.models.product import Product
from app.models.supplier import Supplier
from tests.flow_helpers import draft_po
from tests.invoice_helpers import (
    INVOICES,
    Staff,
    create_invoice,
    invoice_body,
    matched_invoice,
    ordered_po,
    receive,
    received_po,
    submit_invoice,
)

# --- recording an invoice ------------------------------------------------------------------------------------------


async def test_an_invoice_is_recorded_as_a_draft_against_an_order(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)

    invoice = await create_invoice(client, staff.officer, invoice_body(po, product, number="  INV-1 "))

    assert invoice["status"] == "draft"
    assert invoice["invoice_number"] == "INV-1"
    assert invoice["supplier"] == {"id": supplier.id, "name": supplier.name}
    assert invoice["purchase_order"] == {"id": po["id"], "po_number": po["po_number"]}
    assert invoice["currency_code"] == "USD"
    assert (invoice["subtotal"], invoice["tax_total"], invoice["grand_total"]) == ("100.00", "0.00", "100.00")
    assert (invoice["paid_total"], invoice["open_amount"]) == ("0.00", "100.00")
    assert invoice["creator"]["full_name"] == "Purchasing_Officer User"
    assert invoice["exchange_rate"] is None
    assert invoice["base_grand_total"] is None
    [line] = invoice["lines"]
    assert line["product_id"] == product.id
    assert line["description"] == product.name
    assert line["po_item_id"] == po["items"][0]["id"]
    assert (line["line_net"], line["line_total"]) == ("100.00", "100.00")


async def test_the_due_date_defaults_to_the_company_payment_terms(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)

    invoice = await create_invoice(client, staff.officer, invoice_body(po, product))

    assert invoice["due_date"] == (utc_today() + timedelta(days=30)).isoformat()


async def test_the_suppliers_payment_terms_override_the_company_default(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, db_session: AsyncSession
) -> None:
    supplier.payment_terms_days = 45
    db_session.add(supplier)
    await db_session.commit()
    po = await received_po(client, staff, supplier, product)

    invoice = await create_invoice(client, staff.officer, invoice_body(po, product))

    assert invoice["due_date"] == (utc_today() + timedelta(days=45)).isoformat()


async def test_zero_day_terms_make_the_invoice_due_on_its_date(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, db_session: AsyncSession
) -> None:
    supplier.payment_terms_days = 0
    db_session.add(supplier)
    await db_session.commit()
    po = await received_po(client, staff, supplier, product)

    invoice = await create_invoice(client, staff.officer, invoice_body(po, product))

    assert invoice["due_date"] == invoice["invoice_date"]


async def test_an_explicit_due_date_is_kept(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    due = (utc_today() + timedelta(days=5)).isoformat()

    invoice = await create_invoice(client, staff.officer, invoice_body(po, product, due_date=due))

    assert invoice["due_date"] == due


async def test_line_amounts_are_rounded_once_per_line_and_summed(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product, quantity=10, unit_price="3.3333")

    invoice = await create_invoice(client, staff.officer, invoice_body(po, product, quantity=3, unit_price="3.3333"))

    assert invoice["lines"][0]["unit_price"] == "3.3333"
    assert invoice["lines"][0]["line_total"] == "10.00"
    assert invoice["grand_total"] == "10.00"


@pytest.mark.parametrize("progress", ["ordered", "partially_received", "received"])
async def test_invoices_can_be_recorded_against_orders_that_are_ordered_or_received(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, progress: str
) -> None:
    po = await ordered_po(client, staff, supplier, product)
    if progress != "ordered":
        await receive(client, staff, po["id"], product, 4 if progress == "partially_received" else 10)

    response = await client.post(INVOICES, json=invoice_body(po, product, quantity=1), headers=staff.officer)

    assert response.status_code == 201


@pytest.mark.parametrize("stop_after", ["draft", "submitted", "approved", "cancelled"])
async def test_invoices_cannot_be_recorded_against_orders_not_yet_placed_or_cancelled(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, stop_after: str
) -> None:
    po = await draft_po(client, staff.officer, supplier, product)
    base = f"/api/v1/purchase-orders/{po['id']}"
    if stop_after in ("submitted", "approved", "cancelled"):
        await client.post(f"{base}/submit", headers=staff.officer)
    if stop_after in ("approved", "cancelled"):
        await client.post(f"{base}/approve", headers=staff.manager)
    if stop_after == "cancelled":
        await client.post(f"{base}/cancel", headers=staff.officer)

    response = await client.post(INVOICES, json=invoice_body(po, product), headers=staff.officer)

    assert response.status_code == 409
    assert "only be recorded against orders that are ordered or received" in response.json()["detail"]


async def test_the_supplier_must_be_the_orders_supplier(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, db_session: AsyncSession
) -> None:
    other = Supplier(name="Someone Else")
    db_session.add(other)
    await db_session.commit()
    po = await received_po(client, staff, supplier, product)

    wrong = await client.post(INVOICES, json=invoice_body(po, product, supplier_id=other.id), headers=staff.officer)
    right = await client.post(INVOICES, json=invoice_body(po, product, supplier_id=supplier.id), headers=staff.officer)

    assert wrong.status_code == 422
    assert right.status_code == 201


@pytest.mark.parametrize(
    ("override", "status_code"),
    [
        ({"po_id": 99999}, 400),
        ({"invoice_number": "   "}, 422),
        ({"lines": []}, 422),
        ({"due_date": "2000-01-01"}, 422),
        ({"invoice_date": "not-a-date"}, 422),
        ({"lines": [{"product_id": 99999, "quantity": 1, "unit_price": "1.00"}]}, 400),
        ({"lines": [{"quantity": 1, "unit_price": "1.00"}]}, 422),
        ({"lines": [{"description": "x", "quantity": 0, "unit_price": "1.00"}]}, 422),
        ({"lines": [{"description": "x", "quantity": 1, "unit_price": "-1.00"}]}, 422),
        ({"lines": [{"description": "x", "quantity": 1, "unit_price": "1.00001"}]}, 422),
        ({"lines": [{"description": "x", "quantity": 1, "unit_price": "1.00", "tax_rate_id": 99999}]}, 400),
    ],
)
async def test_invalid_invoices_are_refused(
    client: AsyncClient,
    staff: Staff,
    supplier: Supplier,
    product: Product,
    override: dict[str, Any],
    status_code: int,
) -> None:
    po = await received_po(client, staff, supplier, product)

    response = await client.post(INVOICES, json={**invoice_body(po, product), **override}, headers=staff.officer)

    assert response.status_code == status_code


async def test_recording_an_invoice_is_audited(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, db_session: AsyncSession
) -> None:
    po = await received_po(client, staff, supplier, product)
    invoice = await create_invoice(client, staff.officer, invoice_body(po, product, number="INV-AUD"))

    entry = await db_session.scalar(select(AuditLog).where(AuditLog.action == "invoice_created"))

    assert entry is not None
    assert entry.entity_id == invoice["id"]
    assert entry.extra_data is not None
    assert entry.extra_data["invoice_number"] == "INV-AUD"
    assert entry.extra_data["grand_total"] == "100.00"


# --- editing -------------------------------------------------------------------------------------------------------


async def test_a_draft_can_be_edited_and_its_totals_follow_the_new_lines(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    invoice = await create_invoice(client, staff.officer, invoice_body(po, product))

    response = await client.patch(
        f"{INVOICES}/{invoice['id']}",
        json={
            "invoice_number": "INV-2",
            "notes": "Corrected",
            "lines": [{"product_id": product.id, "quantity": 4, "unit_price": "10.00"}],
        },
        headers=staff.officer,
    )

    body = response.json()
    assert response.status_code == 200
    assert (body["invoice_number"], body["notes"], body["grand_total"]) == ("INV-2", "Corrected", "40.00")
    assert [line["quantity"] for line in body["lines"]] == [4]


async def test_moving_the_invoice_date_moves_a_defaulted_due_date_but_not_an_explicit_one(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    invoice = await create_invoice(client, staff.officer, invoice_body(po, product))
    later = (utc_today() + timedelta(days=10)).isoformat()

    moved = await client.patch(f"{INVOICES}/{invoice['id']}", json={"invoice_date": later}, headers=staff.officer)
    explicit = await client.patch(
        f"{INVOICES}/{invoice['id']}",
        json={"invoice_date": later, "due_date": (utc_today() + timedelta(days=12)).isoformat()},
        headers=staff.officer,
    )

    assert moved.json()["due_date"] == (utc_today() + timedelta(days=40)).isoformat()
    assert explicit.json()["due_date"] == (utc_today() + timedelta(days=12)).isoformat()


async def test_an_edit_that_puts_the_due_date_before_the_invoice_date_is_refused(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    invoice = await create_invoice(client, staff.officer, invoice_body(po, product))

    response = await client.patch(f"{INVOICES}/{invoice['id']}", json={"due_date": "2000-01-01"}, headers=staff.officer)

    assert response.status_code == 422


async def test_required_fields_cannot_be_cleared_by_an_edit(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    invoice = await create_invoice(client, staff.officer, invoice_body(po, product))

    response = await client.patch(f"{INVOICES}/{invoice['id']}", json={"due_date": None}, headers=staff.officer)

    assert response.status_code == 422


async def test_only_drafts_can_be_edited(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    invoice = await matched_invoice(client, staff, po, product)

    response = await client.patch(f"{INVOICES}/{invoice['id']}", json={"notes": "late"}, headers=staff.finance)

    assert response.status_code == 409
    assert "Only draft invoices can be edited" in response.json()["detail"]


async def test_an_officer_cannot_edit_or_submit_a_draft_someone_else_recorded(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, auth_headers: Any
) -> None:
    other_officer = await auth_headers("purchasing_officer", "officer2@example.com")
    po = await received_po(client, staff, supplier, product)
    invoice = await create_invoice(client, staff.officer, invoice_body(po, product))

    edit = await client.patch(f"{INVOICES}/{invoice['id']}", json={"notes": "mine now"}, headers=other_officer)
    submit = await submit_invoice(client, other_officer, invoice["id"])
    void = await client.post(f"{INVOICES}/{invoice['id']}/void", json={"reason": "x"}, headers=other_officer)

    assert (edit.status_code, submit.status_code, void.status_code) == (403, 403, 403)
    assert "only change invoices that you recorded" in edit.json()["detail"]


async def test_someone_who_approves_invoices_may_edit_any_draft(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    invoice = await create_invoice(client, staff.officer, invoice_body(po, product))

    response = await client.patch(
        f"{INVOICES}/{invoice['id']}", json={"notes": "fixed by finance"}, headers=staff.finance
    )

    assert response.status_code == 200
