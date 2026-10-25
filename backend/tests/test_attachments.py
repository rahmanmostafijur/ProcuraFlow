from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attachment import Attachment
from app.models.product import Product
from app.models.supplier import Supplier
from app.storage import StoredObjectNotFoundError
from app.storage.local import LocalStorage
from tests.fixture_types import AuthHeaders
from tests.flow_helpers import API, draft_po
from tests.sample_files import image_bytes, pdf_bytes

ATTACHMENTS_URL = f"{API}/attachments"
MAX_BYTES = 10 * 1024 * 1024


async def _upload(
    client: AsyncClient,
    headers: dict[str, str],
    parent_type: str,
    parent_id: int,
    data: bytes,
    name: str = "quote.pdf",
) -> Response:
    return await client.post(
        ATTACHMENTS_URL,
        params={"parent_type": parent_type, "parent_id": parent_id},
        files={"file": (name, data, "application/octet-stream")},
        headers=headers,
    )


async def _request(client: AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
    response = await client.post(
        f"{API}/purchase-requests",
        json={"title": "Chairs", "lines": [{"description": "Chair", "quantity": 1, "estimated_unit_price": "50"}]},
        headers=headers,
    )
    return dict(response.json())


async def test_the_owner_attaches_a_file_to_their_request_and_downloads_it_back(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    employee = await auth_headers("employee")
    request = await _request(client, employee)
    data = pdf_bytes()

    uploaded = await _upload(client, employee, "purchase_request", request["id"], data)
    listed = await client.get(
        ATTACHMENTS_URL, params={"parent_type": "purchase_request", "parent_id": request["id"]}, headers=employee
    )
    download = await client.get(f"{ATTACHMENTS_URL}/{uploaded.json()['id']}/download", headers=employee)

    assert uploaded.status_code == 201
    body = uploaded.json()
    assert (body["filename"], body["content_type"], body["size_bytes"]) == ("quote.pdf", "application/pdf", len(data))
    assert body["uploaded_by"]["full_name"] == "Employee User"
    assert [row["id"] for row in listed.json()] == [body["id"]]
    assert download.status_code == 200
    assert download.content == data
    assert download.headers["content-type"] == "application/pdf"
    assert download.headers["content-disposition"].startswith("attachment; filename*=UTF-8''quote.pdf")
    assert download.headers["x-content-type-options"] == "nosniff"
    assert download.headers["content-security-policy"] == "default-src 'none'; sandbox"
    assert download.headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize(
    ("data", "expected_type"),
    [(pdf_bytes(), "application/pdf"), (image_bytes("PNG"), "image/png"), (image_bytes("JPEG"), "image/jpeg")],
)
async def test_pdf_png_and_jpeg_are_accepted_by_what_they_contain(
    client: AsyncClient, auth_headers: AuthHeaders, data: bytes, expected_type: str
) -> None:
    employee = await auth_headers("employee")
    request = await _request(client, employee)

    # The file name and the client's declared type say nothing; the bytes decide.
    response = await _upload(client, employee, "purchase_request", request["id"], data, name="whatever.bin")

    assert response.status_code == 201
    assert response.json()["content_type"] == expected_type


@pytest.mark.parametrize(
    "data",
    [
        b"<html><script>alert(1)</script></html>",
        b"MZ\x90\x00 an executable pretending to be a document",
        b"PK\x03\x04 a zip archive",
        image_bytes("GIF"),
        b"%PDF" + b"-"[:0],  # one byte short of the PDF signature
    ],
)
async def test_other_kinds_of_file_are_refused_whatever_they_are_called(
    client: AsyncClient, auth_headers: AuthHeaders, data: bytes
) -> None:
    employee = await auth_headers("employee")
    request = await _request(client, employee)

    response = await _upload(client, employee, "purchase_request", request["id"], data, name="invoice.pdf")

    assert response.status_code == 415


async def test_empty_and_oversized_files_are_refused(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    employee = await auth_headers("employee")
    request = await _request(client, employee)

    empty = await _upload(client, employee, "purchase_request", request["id"], b"")
    huge = await _upload(client, employee, "purchase_request", request["id"], pdf_bytes() + b"0" * MAX_BYTES)
    at_the_limit = await _upload(
        client, employee, "purchase_request", request["id"], pdf_bytes() + b"0" * (MAX_BYTES - len(pdf_bytes()))
    )

    assert empty.status_code == 422
    assert huge.status_code == 413
    assert at_the_limit.status_code == 201


async def test_file_names_are_cleaned_and_never_become_paths(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession
) -> None:
    employee = await auth_headers("employee")
    request = await _request(client, employee)

    traversal = await _upload(
        client, employee, "purchase_request", request["id"], pdf_bytes(), name="../../etc/passwd.pdf"
    )
    windows = await _upload(client, employee, "purchase_request", request["id"], pdf_bytes(), name="C:\\temp\\scan.pdf")
    only_dots = await _upload(client, employee, "purchase_request", request["id"], pdf_bytes(), name="...")
    accented = await _upload(
        client, employee, "purchase_request", request["id"], pdf_bytes(), name="Angebot Müller.pdf"
    )

    assert traversal.json()["filename"] == "passwd.pdf"
    assert windows.json()["filename"] == "scan.pdf"
    assert only_dots.json()["filename"] == "file"
    assert accented.json()["filename"] == "Angebot Müller.pdf"
    keys = (await db_session.scalars(select(Attachment.storage_key))).all()
    assert all(key.startswith("attachments/") and ".." not in key and "passwd" not in key for key in keys)


async def test_a_record_holds_at_most_twenty_attachments(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    employee = await auth_headers("employee")
    request = await _request(client, employee)
    png = image_bytes("PNG")

    for _ in range(20):
        assert (
            await _upload(client, employee, "purchase_request", request["id"], png, name="a.png")
        ).status_code == 201
    overflow = await _upload(client, employee, "purchase_request", request["id"], png, name="a.png")

    assert overflow.status_code == 409


async def test_nobody_else_can_reach_a_requests_files_by_changing_ids(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    alice = await auth_headers("employee", email="alice@example.com")
    bob = await auth_headers("employee", email="bob@example.com")
    request = await _request(client, alice)
    attachment = (await _upload(client, alice, "purchase_request", request["id"], pdf_bytes())).json()
    params = {"parent_type": "purchase_request", "parent_id": request["id"]}

    results = [
        await client.get(ATTACHMENTS_URL, params=params, headers=bob),
        await client.get(f"{ATTACHMENTS_URL}/{attachment['id']}/download", headers=bob),
        await _upload(client, bob, "purchase_request", request["id"], pdf_bytes()),
        await client.delete(f"{ATTACHMENTS_URL}/{attachment['id']}", headers=bob),
    ]

    assert [result.status_code for result in results] == [404, 404, 404, 404]
    assert (await client.get(f"{ATTACHMENTS_URL}/{attachment['id']}/download", headers=alice)).status_code == 200


async def test_people_who_see_every_request_can_read_its_files_but_not_change_them(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    employee = await auth_headers("employee")
    officer = await auth_headers("purchasing_officer")
    request = await _request(client, employee)
    attachment = (await _upload(client, employee, "purchase_request", request["id"], pdf_bytes())).json()

    listed = await client.get(
        ATTACHMENTS_URL, params={"parent_type": "purchase_request", "parent_id": request["id"]}, headers=officer
    )
    download = await client.get(f"{ATTACHMENTS_URL}/{attachment['id']}/download", headers=officer)
    upload = await _upload(client, officer, "purchase_request", request["id"], pdf_bytes())
    delete = await client.delete(f"{ATTACHMENTS_URL}/{attachment['id']}", headers=officer)

    assert listed.status_code == 200
    assert download.status_code == 200
    assert upload.status_code == 403
    assert delete.status_code == 403


async def test_an_approver_can_open_the_files_of_a_request_they_must_decide(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    employee = await auth_headers("employee")
    manager = await auth_headers("department_manager")
    request = await _request(client, employee)
    attachment = (await _upload(client, employee, "purchase_request", request["id"], pdf_bytes())).json()
    await client.post(f"{API}/purchase-requests/{request['id']}/submit", headers=employee)

    response = await client.get(f"{ATTACHMENTS_URL}/{attachment['id']}/download", headers=manager)

    assert response.status_code == 200


async def test_files_can_be_added_while_a_request_is_waiting_but_not_once_it_is_decided(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    employee = await auth_headers("employee")
    manager = await auth_headers("department_manager")
    request = await _request(client, employee)
    await client.post(f"{API}/purchase-requests/{request['id']}/submit", headers=employee)

    while_waiting = await _upload(client, employee, "purchase_request", request["id"], pdf_bytes())
    await client.post(f"{API}/purchase-requests/{request['id']}/approve", headers=manager)
    after_approval = await _upload(client, employee, "purchase_request", request["id"], pdf_bytes())

    assert while_waiting.status_code == 201
    assert after_approval.status_code == 403


async def test_the_owner_can_remove_a_file_and_it_is_gone_from_storage(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession, storage: LocalStorage
) -> None:
    employee = await auth_headers("employee")
    request = await _request(client, employee)
    attachment = (await _upload(client, employee, "purchase_request", request["id"], pdf_bytes())).json()
    key = (await db_session.scalar(select(Attachment.storage_key).where(Attachment.id == attachment["id"]))) or ""

    removed = await client.delete(f"{ATTACHMENTS_URL}/{attachment['id']}", headers=employee)
    after = await client.get(f"{ATTACHMENTS_URL}/{attachment['id']}/download", headers=employee)

    assert removed.status_code == 204
    assert after.status_code == 404
    with pytest.raises(StoredObjectNotFoundError):
        await storage.read(key)


async def test_purchase_order_files_follow_the_orders_permissions(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    officer = await auth_headers("purchasing_officer")
    viewer = await auth_headers("viewer")
    po = await draft_po(client, officer, supplier, product)

    by_officer = await _upload(client, officer, "purchase_order", po["id"], pdf_bytes(), name="contract.pdf")
    by_viewer = await _upload(client, viewer, "purchase_order", po["id"], pdf_bytes())
    listed_by_viewer = await client.get(
        ATTACHMENTS_URL, params={"parent_type": "purchase_order", "parent_id": po["id"]}, headers=viewer
    )
    downloaded_by_viewer = await client.get(f"{ATTACHMENTS_URL}/{by_officer.json()['id']}/download", headers=viewer)

    assert by_officer.status_code == 201
    assert by_viewer.status_code == 403
    assert listed_by_viewer.status_code == 200
    assert downloaded_by_viewer.status_code == 200


async def test_unknown_records_files_and_missing_sign_in(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    employee = await auth_headers("employee")

    unknown_parent = await client.get(
        ATTACHMENTS_URL, params={"parent_type": "purchase_request", "parent_id": 99999}, headers=employee
    )
    upload_to_unknown = await _upload(client, employee, "purchase_request", 99999, pdf_bytes())
    unknown_file = await client.get(f"{ATTACHMENTS_URL}/99999/download", headers=employee)
    bad_type = await client.get(ATTACHMENTS_URL, params={"parent_type": "supplier", "parent_id": 1}, headers=employee)
    anonymous = await client.get(ATTACHMENTS_URL, params={"parent_type": "purchase_request", "parent_id": 1})
    anonymous_download = await client.get(f"{ATTACHMENTS_URL}/1/download")

    assert (unknown_parent.status_code, upload_to_unknown.status_code, unknown_file.status_code) == (404, 404, 404)
    assert bad_type.status_code == 422
    assert (anonymous.status_code, anonymous_download.status_code) == (401, 401)
