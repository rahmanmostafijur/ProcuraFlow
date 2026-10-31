"""Which files an attachment may be, decided by their bytes, and who may download them."""

import io
import zipfile
from typing import Any

import pytest
from httpx import AsyncClient, Response

from app.core import file_types
from app.core.file_types import ATTACHMENT_KINDS, DOCUMENT_KINDS, detect_file_type
from tests.fixture_types import AuthHeaders
from tests.flow_helpers import API
from tests.sample_files import csv_bytes, image_bytes, pdf_bytes, xlsx_bytes

ATTACHMENTS_URL = f"{API}/attachments"
XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


async def _request(client: AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
    response = await client.post(
        f"{API}/purchase-requests",
        json={"title": "Chairs", "lines": [{"description": "Chair", "quantity": 1, "estimated_unit_price": "50"}]},
        headers=headers,
    )
    return dict(response.json())


async def _upload(client: AsyncClient, headers: dict[str, str], request_id: int, data: bytes, name: str) -> Response:
    return await client.post(
        ATTACHMENTS_URL,
        params={"parent_type": "purchase_request", "parent_id": request_id},
        files={"file": (name, data, "application/octet-stream")},
        headers=headers,
    )


def _zip_with(*names: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in names:
            archive.writestr(name, "<x/>")
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("data", "content_type"),
    [
        (pdf_bytes(), "application/pdf"),
        (image_bytes("PNG"), "image/png"),
        (image_bytes("JPEG"), "image/jpeg"),
        (xlsx_bytes(), XLSX_TYPE),
        (csv_bytes(), "text/csv"),
        (b"\xef\xbb\xbfname;total\r\nAcme;10\r\n", "text/csv"),
    ],
)
async def test_pdf_png_jpeg_xlsx_and_csv_are_accepted_and_served_back(
    client: AsyncClient, auth_headers: AuthHeaders, data: bytes, content_type: str
) -> None:
    employee = await auth_headers("employee")
    request = await _request(client, employee)

    uploaded = await _upload(client, employee, request["id"], data, "whatever.bin")
    download = await client.get(f"{ATTACHMENTS_URL}/{uploaded.json()['id']}/download", headers=employee)

    assert uploaded.status_code == 201
    assert uploaded.json()["content_type"] == content_type
    assert download.content == data
    assert download.headers["content-type"].startswith(content_type)
    assert download.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize(
    "data",
    [
        _zip_with("hello.txt"),  # a plain zip is not a workbook
        _zip_with("[Content_Types].xml", "word/document.xml"),  # a docx is not a workbook
        b"PK\x03\x04 truncated",
        b"<html>a,b,c</html>",
        b"just a sentence without any table in it",
        b"a,b\x00c\n1,2,3\n",
        b"\xff\xfe binary, not utf-8",
    ],
)
async def test_spreadsheet_and_text_look_alikes_are_refused(
    client: AsyncClient, auth_headers: AuthHeaders, data: bytes
) -> None:
    employee = await auth_headers("employee")
    request = await _request(client, employee)

    response = await _upload(client, employee, request["id"], data, "sheet.xlsx")

    assert response.status_code == 415
    assert "Excel" in response.json()["detail"]


def test_document_uploads_do_not_accept_spreadsheets_or_csv() -> None:
    assert detect_file_type(xlsx_bytes(), DOCUMENT_KINDS) is None
    assert detect_file_type(csv_bytes(), DOCUMENT_KINDS) is None
    assert detect_file_type(pdf_bytes(), DOCUMENT_KINDS) == ("application/pdf", "pdf")
    assert detect_file_type(xlsx_bytes(), ATTACHMENT_KINDS) is not None


def test_a_zip_bomb_is_not_opened_as_a_workbook(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(file_types, "_MAX_UNCOMPRESSED_BYTES", 5)

    assert detect_file_type(xlsx_bytes(), ATTACHMENT_KINDS) is None


async def test_a_spreadsheet_download_is_only_for_people_who_can_see_the_record(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    owner = await auth_headers("employee")
    other_employee = await auth_headers("employee", "other@example.com")
    request = await _request(client, owner)
    uploaded = await _upload(client, owner, request["id"], xlsx_bytes(), "plan.xlsx")
    url = f"{ATTACHMENTS_URL}/{uploaded.json()['id']}/download"

    stranger = await client.get(url, headers=other_employee)
    anonymous = await client.get(url)

    assert stranger.status_code == 404
    assert anonymous.status_code == 401
