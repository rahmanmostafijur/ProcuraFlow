from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.product import Product
from app.models.supplier import Supplier
from tests.fixture_types import AuthHeaders
from tests.invoice_helpers import (
    INVOICES,
    Staff,
    create_invoice,
    invoice_body,
    matched_invoice,
    received_po,
    submit_invoice,
)
from tests.sample_files import image_bytes, pdf_bytes

ATTACHMENTS = "/api/v1/attachments"


async def _upload(
    client: AsyncClient, headers: dict[str, str], invoice_id: int, data: bytes | None = None, name: str = "bill.pdf"
) -> Response:
    return await client.post(
        ATTACHMENTS,
        params={"parent_type": "supplier_invoice", "parent_id": invoice_id},
        files={"file": (name, data or pdf_bytes(), "application/octet-stream")},
        headers=headers,
    )


async def _draft(client: AsyncClient, staff: Staff, supplier: Supplier, product: Product) -> dict[str, Any]:
    po = await received_po(client, staff, supplier, product)
    return await create_invoice(client, staff.officer, invoice_body(po, product))


async def test_the_person_who_recorded_a_draft_attaches_a_pdf_and_everyone_who_reads_invoices_can_open_it(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    invoice = await _draft(client, staff, supplier, product)
    data = pdf_bytes()

    uploaded = await _upload(client, staff.officer, invoice["id"], data)
    listed = await client.get(
        ATTACHMENTS, params={"parent_type": "supplier_invoice", "parent_id": invoice["id"]}, headers=staff.manager
    )
    download = await client.get(f"{ATTACHMENTS}/{uploaded.json()['id']}/download", headers=staff.finance)

    assert uploaded.status_code == 201
    assert uploaded.json()["parent_type"] == "supplier_invoice"
    assert [row["filename"] for row in listed.json()] == ["bill.pdf"]
    assert download.status_code == 200
    assert download.content == data


async def test_an_image_scan_can_be_attached_too(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    invoice = await _draft(client, staff, supplier, product)

    response = await _upload(client, staff.officer, invoice["id"], image_bytes("JPEG"), name="scan.jpg")

    assert response.status_code == 201
    assert response.json()["content_type"] == "image/jpeg"


@pytest.mark.parametrize("role", ["viewer", "warehouse"])
async def test_people_who_cannot_read_invoices_get_not_found_for_its_attachments(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, role: str
) -> None:
    invoice = await _draft(client, staff, supplier, product)
    uploaded = (await _upload(client, staff.officer, invoice["id"])).json()
    headers = getattr(staff, role)

    listed = await client.get(
        ATTACHMENTS, params={"parent_type": "supplier_invoice", "parent_id": invoice["id"]}, headers=headers
    )
    download = await client.get(f"{ATTACHMENTS}/{uploaded['id']}/download", headers=headers)
    upload = await _upload(client, headers, invoice["id"])
    delete = await client.delete(f"{ATTACHMENTS}/{uploaded['id']}", headers=headers)

    assert [listed.status_code, download.status_code, upload.status_code, delete.status_code] == [404] * 4


async def test_an_unknown_invoice_has_no_attachments(client: AsyncClient, staff: Staff) -> None:
    listed = await client.get(
        ATTACHMENTS, params={"parent_type": "supplier_invoice", "parent_id": 99999}, headers=staff.finance
    )
    upload = await _upload(client, staff.finance, 99999)

    assert listed.status_code == 404
    assert upload.status_code == 404


async def test_someone_with_invoice_write_who_did_not_record_the_invoice_cannot_attach_to_it(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, auth_headers: AuthHeaders
) -> None:
    other_officer = await auth_headers("purchasing_officer", "officer2@example.com")
    invoice = await _draft(client, staff, supplier, product)

    response = await _upload(client, other_officer, invoice["id"])

    assert response.status_code == 403
    assert response.json()["detail"] == "You cannot attach files to this record"


async def test_someone_who_approves_invoices_can_attach_to_any_draft(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    invoice = await _draft(client, staff, supplier, product)

    response = await _upload(client, staff.finance, invoice["id"])

    assert response.status_code == 201


async def test_attachments_can_be_added_to_an_exception_and_to_an_invoice_on_hold(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    invoice = await create_invoice(client, staff.officer, invoice_body(po, product, unit_price="30.00"))
    await submit_invoice(client, staff.officer, invoice["id"])

    on_exception = await _upload(client, staff.officer, invoice["id"], name="credit-note.pdf")
    await client.post(f"{INVOICES}/{invoice['id']}/hold", json={"reason": "Query"}, headers=staff.finance)
    on_hold = await _upload(client, staff.officer, invoice["id"], name="reply.pdf")

    assert on_exception.status_code == 201
    assert on_hold.status_code == 201


async def test_attachments_are_closed_once_the_invoice_is_matched_but_stay_readable(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    invoice = await create_invoice(client, staff.officer, invoice_body(po, product))
    uploaded = (await _upload(client, staff.officer, invoice["id"])).json()
    await submit_invoice(client, staff.officer, invoice["id"])

    add = await _upload(client, staff.officer, invoice["id"])
    remove = await client.delete(f"{ATTACHMENTS}/{uploaded['id']}", headers=staff.officer)
    download = await client.get(f"{ATTACHMENTS}/{uploaded['id']}/download", headers=staff.officer)

    assert add.status_code == 403
    assert remove.status_code == 403
    assert download.status_code == 200


async def test_approved_and_void_invoices_take_no_new_attachments(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    invoice = await matched_invoice(client, staff, po, product)
    await client.post(f"{INVOICES}/{invoice['id']}/approve", headers=staff.finance)
    approved = await _upload(client, staff.finance, invoice["id"])
    await client.post(f"{INVOICES}/{invoice['id']}/void", json={"reason": "x"}, headers=staff.finance)
    voided = await _upload(client, staff.finance, invoice["id"])

    assert approved.status_code == 403
    assert voided.status_code == 403


async def test_a_draft_attachment_can_be_removed_by_the_person_who_may_write_to_it(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    invoice = await _draft(client, staff, supplier, product)
    uploaded = (await _upload(client, staff.officer, invoice["id"])).json()

    removed = await client.delete(f"{ATTACHMENTS}/{uploaded['id']}", headers=staff.officer)
    listed = await client.get(
        ATTACHMENTS, params={"parent_type": "supplier_invoice", "parent_id": invoice["id"]}, headers=staff.officer
    )

    assert removed.status_code == 204
    assert listed.json() == []


async def test_attachment_changes_are_audited_against_the_invoice(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, db_session: AsyncSession
) -> None:
    invoice = await _draft(client, staff, supplier, product)
    uploaded = (await _upload(client, staff.officer, invoice["id"])).json()
    await client.delete(f"{ATTACHMENTS}/{uploaded['id']}", headers=staff.officer)

    entries = (
        await db_session.scalars(
            select(AuditLog).where(AuditLog.entity_type == "supplier_invoice", AuditLog.action.like("attachment_%"))
        )
    ).all()

    assert sorted(entry.action for entry in entries) == ["attachment_removed", "attachment_uploaded"]
    assert {entry.entity_id for entry in entries} == {invoice["id"]}
