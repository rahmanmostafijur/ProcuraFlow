"""The supplier portal: what a supplier sees and does, and how the invitation creates the account."""

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_today
from app.models.attachment import Attachment
from app.models.audit import AuditLog
from app.models.enums import InvoiceStatus
from app.models.product import Product
from app.models.role import Role
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice
from tests.flow_helpers import API, draft_po, submitted_po
from tests.invoice_helpers import Staff, approved_invoice, received_po
from tests.portal_helpers import (
    PORTAL,
    Tenant,
    draft_invoice,
    invoice_file,
    invoice_payload,
    tenant,
)
from tests.sample_files import csv_bytes, image_bytes, pdf_bytes, xlsx_bytes


@pytest.fixture
async def acme(
    client: AsyncClient,
    db_session: AsyncSession,
    roles: dict[str, Role],
    staff: Staff,
    supplier: Supplier,
    product: Product,
) -> Tenant:
    return await tenant(client, db_session, roles, staff, supplier, product, "portal@acme.example.com")


async def test_a_supplier_sees_who_and_which_supplier_it_is(client: AsyncClient, acme: Tenant) -> None:
    response = await client.get(f"{PORTAL}/me", headers=acme.headers)

    assert response.status_code == 200
    assert response.json()["email"] == "portal@acme.example.com"
    assert response.json()["supplier"] == {"id": acme.supplier.id, "name": "Test Supplier"}


async def test_only_placed_orders_are_visible_never_drafts_or_unapproved_ones(
    client: AsyncClient, acme: Tenant, staff: Staff
) -> None:
    draft = await draft_po(client, staff.officer, acme.supplier, acme.product)
    submitted = await submitted_po(client, staff.officer, acme.supplier, acme.product)
    received = await received_po(client, staff, acme.supplier, acme.product)

    listed = (await client.get(f"{PORTAL}/orders", headers=acme.headers)).json()
    ids = {row["id"] for row in listed["items"]}

    assert ids == {acme.order["id"], received["id"]}
    assert {row["status"] for row in listed["items"]} == {"ordered", "received"}
    for hidden in (draft["id"], submitted["id"]):
        assert (await client.get(f"{PORTAL}/orders/{hidden}", headers=acme.headers)).status_code == 404
        assert (await client.post(f"{PORTAL}/orders/{hidden}/acknowledge", headers=acme.headers)).status_code == 404
    by_status = (await client.get(f"{PORTAL}/orders", params={"status": "received"}, headers=acme.headers)).json()
    assert [row["id"] for row in by_status["items"]] == [received["id"]]


async def test_an_order_shows_lines_totals_and_nothing_internal(client: AsyncClient, acme: Tenant) -> None:
    response = await client.get(f"{PORTAL}/orders/{acme.order['id']}", headers=acme.headers)

    body = response.json()
    assert body["po_number"] == acme.order["po_number"]
    assert (body["currency_code"], body["grand_total"], body["acknowledged_at"]) == ("USD", "100.00", None)
    assert body["items"][0]["product_name"] == "Test Widget"
    assert (body["items"][0]["quantity"], body["items"][0]["unit_price"], body["items"][0]["line_total"]) == (
        10,
        "10.00",
        "100.00",
    )
    internal = {"creator", "approver", "notes", "exchange_rate", "base_grand_total", "cost_centre_id", "supplier"}
    assert not internal & body.keys()


async def test_acknowledging_is_idempotent_and_recorded_once(
    client: AsyncClient, acme: Tenant, staff: Staff, db_session: AsyncSession
) -> None:
    url = f"{PORTAL}/orders/{acme.order['id']}/acknowledge"

    first = await client.post(url, headers=acme.headers)
    second = await client.post(url, headers=acme.headers)

    assert (first.status_code, second.status_code) == (200, 200)
    assert first.json()["acknowledged_at"] is not None
    assert second.json()["acknowledged_at"] == first.json()["acknowledged_at"]
    events = (await db_session.execute(select(AuditLog).where(AuditLog.action == "po_acknowledged"))).scalars().all()
    assert len(events) == 1
    assert events[0].entity_id == acme.order["id"]
    internal = await client.get(f"{API}/purchase-orders/{acme.order['id']}", headers=staff.officer)
    assert internal.json()["acknowledged_at"] == first.json()["acknowledged_at"]


async def test_an_invoice_arrives_as_a_draft_priced_from_the_order(
    client: AsyncClient, acme: Tenant, staff: Staff, db_session: AsyncSession
) -> None:
    created = await client.post(f"{PORTAL}/invoices", json=invoice_payload(acme), headers=acme.headers)

    assert created.status_code == 201
    body = created.json()
    assert (body["status"], body["grand_total"], body["paid_total"], body["open_amount"]) == (
        "draft",
        "100.00",
        "0.00",
        "100.00",
    )
    assert body["po_number"] == acme.order["po_number"]
    stored = await db_session.scalar(select(SupplierInvoice))
    assert stored is not None
    assert (stored.supplier_id, stored.po_id, stored.currency_code) == (acme.supplier.id, acme.order["id"], "USD")
    # Finance sees it in the normal invoice list, and it is the supplier's own account that created it.
    internal = await client.get(f"{API}/supplier-invoices/{body['id']}", headers=staff.finance)
    assert internal.status_code == 200
    assert internal.json()["creator"]["full_name"].startswith("Portal portal")


async def test_a_second_invoice_with_the_same_number_is_refused_whatever_its_case(
    client: AsyncClient, acme: Tenant
) -> None:
    await draft_invoice(client, acme, "INV-77")

    same = await client.post(f"{PORTAL}/invoices", json=invoice_payload(acme, " inv-77 "), headers=acme.headers)

    assert same.status_code == 409
    assert "already sent an invoice" in same.json()["detail"]


async def test_the_invoice_is_checked_by_the_normal_rules(client: AsyncClient, acme: Tenant) -> None:
    unknown_product = invoice_payload(acme, lines=[{"product_id": 999999, "quantity": 1, "unit_price": "1.00"}])
    no_lines = invoice_payload(acme, lines=[])
    negative = invoice_payload(acme, lines=[{"product_id": acme.product.id, "quantity": 1, "unit_price": "-1"}])
    backwards = invoice_payload(acme, "B-1", due_date=(utc_today() - timedelta(days=5)).isoformat())

    assert (await client.post(f"{PORTAL}/invoices", json=unknown_product, headers=acme.headers)).status_code == 422
    assert (await client.post(f"{PORTAL}/invoices", json=no_lines, headers=acme.headers)).status_code == 422
    assert (await client.post(f"{PORTAL}/invoices", json=negative, headers=acme.headers)).status_code == 422
    assert (await client.post(f"{PORTAL}/invoices", json=backwards, headers=acme.headers)).status_code == 422


async def test_a_supplier_cannot_set_the_supplier_the_currency_or_the_tax(
    client: AsyncClient, acme: Tenant, db_session: AsyncSession
) -> None:
    payload = invoice_payload(acme, supplier_id=12345, currency_code="EUR", status="paid", created_by=1)
    payload["lines"][0]["tax_rate_id"] = 999

    created = await client.post(f"{PORTAL}/invoices", json=payload, headers=acme.headers)

    assert created.status_code == 201
    stored = await db_session.scalar(select(SupplierInvoice))
    assert stored is not None
    assert (stored.supplier_id, stored.currency_code, stored.status) == (acme.supplier.id, "USD", InvoiceStatus.DRAFT)
    assert stored.tax_total == 0


async def test_an_invoice_can_have_a_pdf_or_image_attached_while_it_is_a_draft(
    client: AsyncClient, acme: Tenant, staff: Staff, db_session: AsyncSession
) -> None:
    invoice = await draft_invoice(client, acme)
    url = f"{PORTAL}/invoices/{invoice['id']}/files"

    pdf = await invoice_file(client, acme, invoice["id"])
    photo = await client.post(url, files={"file": ("scan.png", image_bytes("PNG"), "image/png")}, headers=acme.headers)
    sheet = await client.post(url, files={"file": ("a.xlsx", xlsx_bytes(), "x/y")}, headers=acme.headers)
    table = await client.post(url, files={"file": ("a.csv", csv_bytes(), "x/y")}, headers=acme.headers)
    disguised = await client.post(
        url, files={"file": ("a.pdf", b"<html></html>", "application/pdf")}, headers=acme.headers
    )
    listed = await client.get(url, headers=acme.headers)
    download = await client.get(f"{url}/{pdf['id']}/download", headers=acme.headers)

    assert photo.status_code == 201
    assert (sheet.status_code, table.status_code, disguised.status_code) == (415, 415, 415)
    assert listed.json()[0]["id"] == pdf["id"]
    assert download.content == pdf_bytes()
    assert download.headers["x-content-type-options"] == "nosniff"
    # Finance can open the same file through the normal attachment screens.
    internal = await client.get(
        f"{API}/attachments",
        params={"parent_type": "supplier_invoice", "parent_id": invoice["id"]},
        headers=staff.finance,
    )
    assert len(internal.json()) == 2
    assert await db_session.scalar(select(func.count()).select_from(Attachment)) == 2


async def test_files_cannot_be_added_once_the_invoice_is_past_draft(
    client: AsyncClient, acme: Tenant, staff: Staff
) -> None:
    po = await received_po(client, staff, acme.supplier, acme.product)
    invoice = await client.post(
        f"{PORTAL}/invoices",
        json=invoice_payload(Tenant(acme.supplier, acme.product, acme.headers, po), "LATE-1"),
        headers=acme.headers,
    )
    submitted = await client.post(f"{API}/supplier-invoices/{invoice.json()['id']}/submit", headers=staff.finance)

    late = await client.post(
        f"{PORTAL}/invoices/{invoice.json()['id']}/files",
        files={"file": ("a.pdf", pdf_bytes(), "x/y")},
        headers=acme.headers,
    )

    assert submitted.status_code == 200
    assert late.status_code == 409


async def test_the_supplier_follows_the_invoice_through_its_statuses(
    client: AsyncClient, acme: Tenant, staff: Staff
) -> None:
    po = await received_po(client, staff, acme.supplier, acme.product)
    approved = await approved_invoice(client, staff, po, acme.product, number="APPROVED-1")
    draft = await draft_invoice(client, acme, "DRAFT-1")

    everything = (await client.get(f"{PORTAL}/invoices", headers=acme.headers)).json()
    only_approved = (await client.get(f"{PORTAL}/invoices", params={"status": "approved"}, headers=acme.headers)).json()
    detail = await client.get(f"{PORTAL}/invoices/{approved['id']}", headers=acme.headers)

    assert {row["invoice_number"]: row["status"] for row in everything["items"]} == {
        "APPROVED-1": "approved",
        "DRAFT-1": "draft",
    }
    assert [row["id"] for row in only_approved["items"]] == [approved["id"]]
    assert detail.status_code == 200
    assert draft["status"] == "draft"
    assert not {"exception_reasons", "creator", "approver", "hold_reason", "rejection_reason"} & detail.json().keys()


async def test_documents_are_managed_by_the_supplier_itself(
    client: AsyncClient, acme: Tenant, staff: Staff, db_session: AsyncSession
) -> None:
    created = await client.post(
        f"{PORTAL}/documents",
        data={"document_type": "insurance", "issue_date": "2026-01-01", "expiry_date": "2099-01-01"},
        files={"file": ("cert.pdf", pdf_bytes(), "application/pdf")},
        headers=acme.headers,
    )
    document_id = created.json()["id"]
    listed = await client.get(f"{PORTAL}/documents", headers=acme.headers)
    download = await client.get(f"{PORTAL}/documents/{document_id}/download", headers=acme.headers)
    internal = await client.get(f"{API}/suppliers/{acme.supplier.id}/documents", headers=staff.manager)
    bad_file = await client.post(
        f"{PORTAL}/documents",
        data={"document_type": "w9"},
        files={"file": ("w9.xlsx", xlsx_bytes(), "x/y")},
        headers=acme.headers,
    )
    deleted = await client.delete(f"{PORTAL}/documents/{document_id}", headers=acme.headers)

    assert created.status_code == 201
    assert created.json()["status"] == "valid"
    assert [row["id"] for row in listed.json()] == [document_id]
    assert download.content == pdf_bytes()
    assert [row["id"] for row in internal.json()] == [document_id]
    assert bad_file.status_code == 415
    assert deleted.status_code == 204
    assert (await client.get(f"{PORTAL}/documents", headers=acme.headers)).json() == []
    actions = (
        (await db_session.execute(select(AuditLog.action).where(AuditLog.action.like("supplier_document_%"))))
        .scalars()
        .all()
    )
    assert sorted(actions) == ["supplier_document_removed", "supplier_document_uploaded"]
