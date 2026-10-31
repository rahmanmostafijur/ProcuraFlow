"""Supplier documents: upload, list, delete, the computed expiry status and the daily expiry notifications."""

from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, timedelta

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.audit import AuditLog
from app.models.enums import SupplierDocumentStatus
from app.models.notification import Notification
from app.models.supplier import Supplier
from app.models.supplier_document import SupplierDocument
from app.services.notification_service import notify_expiring_supplier_documents
from app.services.supplier_document_service import document_status
from app.services.today import get_today
from app.storage import StoredObjectNotFoundError
from app.storage.local import LocalStorage
from tests.fixture_types import AuthHeaders
from tests.flow_helpers import API
from tests.sample_files import csv_bytes, image_bytes, pdf_bytes, xlsx_bytes

TODAY = date(2026, 6, 15)
VALID, SOON, EXPIRED = (
    SupplierDocumentStatus.VALID,
    SupplierDocumentStatus.EXPIRING_SOON,
    SupplierDocumentStatus.EXPIRED,
)


@pytest.fixture
def today_is() -> Iterator[Callable[[date], None]]:
    """Pin the date the API considers to be today."""

    def _set(day: date) -> None:
        app.dependency_overrides[get_today] = lambda: day

    _set(TODAY)
    yield _set
    app.dependency_overrides.pop(get_today, None)


def _documents_url(supplier_id: int) -> str:
    return f"{API}/suppliers/{supplier_id}/documents"


async def _upload(
    client: AsyncClient,
    headers: dict[str, str],
    supplier_id: int,
    *,
    document_type: str = "w9",
    issue_date: date | None = None,
    expiry_date: date | None = None,
    data: bytes | None = None,
    name: str = "scan.pdf",
) -> Response:
    form = {"document_type": document_type}
    if issue_date:
        form["issue_date"] = issue_date.isoformat()
    if expiry_date:
        form["expiry_date"] = expiry_date.isoformat()
    return await client.post(
        _documents_url(supplier_id),
        data=form,
        files={"file": (name, data if data is not None else pdf_bytes(), "application/octet-stream")},
        headers=headers,
    )


@pytest.fixture
async def manager(auth_headers: AuthHeaders) -> dict[str, str]:
    return await auth_headers("procurement_manager")


@pytest.fixture
async def other_supplier(db_session: AsyncSession) -> Supplier:
    other = Supplier(name="Other Co")
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)
    return other


@pytest.mark.parametrize(
    ("days_from_today", "expected"),
    [(None, VALID), (-1, EXPIRED), (0, SOON), (1, SOON), (30, SOON), (31, VALID), (365, VALID), (-400, EXPIRED)],
)
def test_the_status_follows_the_expiry_date_and_todays_date(
    days_from_today: int | None, expected: SupplierDocumentStatus
) -> None:
    expiry = None if days_from_today is None else TODAY + timedelta(days=days_from_today)

    assert document_status(expiry, TODAY) == expected


def test_the_status_is_never_a_stored_column() -> None:
    assert "status" not in SupplierDocument.__table__.columns


async def test_a_document_is_uploaded_listed_and_downloaded(
    client: AsyncClient, manager: dict[str, str], supplier: Supplier, today_is: Callable[[date], None]
) -> None:
    data = pdf_bytes()

    uploaded = await _upload(
        client,
        manager,
        supplier.id,
        document_type="insurance",
        issue_date=date(2026, 1, 1),
        expiry_date=date(2026, 7, 1),
        data=data,
    )
    listed = await client.get(_documents_url(supplier.id), headers=manager)
    download = await client.get(f"{_documents_url(supplier.id)}/{uploaded.json()['id']}/download", headers=manager)

    assert uploaded.status_code == 201
    body = uploaded.json()
    assert (body["document_type"], body["status"], body["days_until_expiry"]) == ("insurance", "expiring_soon", 16)
    assert body["content_type"] == "application/pdf"
    assert [row["id"] for row in listed.json()] == [body["id"]]
    assert download.content == data
    assert download.headers["x-content-type-options"] == "nosniff"


async def test_the_status_changes_with_the_date_without_anything_being_saved(
    client: AsyncClient,
    manager: dict[str, str],
    supplier: Supplier,
    today_is: Callable[[date], None],
    db_session: AsyncSession,
) -> None:
    await _upload(client, manager, supplier.id, expiry_date=date(2026, 8, 31))

    async def status_on(day: date) -> str:
        today_is(day)
        return str((await client.get(_documents_url(supplier.id), headers=manager)).json()[0]["status"])

    assert await status_on(date(2026, 6, 15)) == "valid"
    assert await status_on(date(2026, 8, 1)) == "expiring_soon"
    assert await status_on(date(2026, 9, 1)) == "expired"
    assert await status_on(date(2026, 6, 15)) == "valid"
    stored = await db_session.scalar(select(SupplierDocument.expiry_date))
    assert stored == date(2026, 8, 31)


async def test_the_dates_must_be_in_order_and_the_file_must_be_a_document(
    client: AsyncClient, manager: dict[str, str], supplier: Supplier
) -> None:
    backwards = await _upload(client, manager, supplier.id, issue_date=date(2026, 5, 1), expiry_date=date(2026, 4, 1))
    sheet = await _upload(client, manager, supplier.id, data=xlsx_bytes(), name="w9.xlsx")
    table = await _upload(client, manager, supplier.id, data=csv_bytes(), name="w9.csv")
    empty = await _upload(client, manager, supplier.id, data=b"")
    photo = await _upload(client, manager, supplier.id, data=image_bytes("JPEG"), name="w9.jpg")
    bad_type = await _upload(client, manager, supplier.id, document_type="passport")

    assert backwards.status_code == 422
    assert (sheet.status_code, table.status_code, empty.status_code) == (415, 415, 422)
    assert photo.status_code == 201
    assert bad_type.status_code == 422


async def test_only_people_who_manage_suppliers_can_use_documents(
    client: AsyncClient, auth_headers: AuthHeaders, manager: dict[str, str], supplier: Supplier
) -> None:
    uploaded = await _upload(client, manager, supplier.id)
    document_id = uploaded.json()["id"]
    urls = [
        ("GET", _documents_url(supplier.id)),
        ("GET", f"{_documents_url(supplier.id)}/{document_id}/download"),
        ("DELETE", f"{_documents_url(supplier.id)}/{document_id}"),
        ("GET", f"{API}/supplier-documents/expiring"),
    ]

    for role in ("viewer", "finance", "purchasing_officer", "warehouse_manager"):
        headers = await auth_headers(role)
        assert (await _upload(client, headers, supplier.id)).status_code == 403
        for method, url in urls:
            assert (await client.request(method, url, headers=headers)).status_code == 403
    for method, url in urls:
        assert (await client.request(method, url)).status_code == 401


async def test_a_document_cannot_be_reached_through_another_suppliers_url(
    client: AsyncClient, manager: dict[str, str], supplier: Supplier, other_supplier: Supplier
) -> None:
    document_id = (await _upload(client, manager, supplier.id)).json()["id"]

    download = await client.get(f"{_documents_url(other_supplier.id)}/{document_id}/download", headers=manager)
    delete = await client.delete(f"{_documents_url(other_supplier.id)}/{document_id}", headers=manager)
    other_list = await client.get(_documents_url(other_supplier.id), headers=manager)
    unknown = await client.get(_documents_url(9999), headers=manager)

    assert (download.status_code, delete.status_code) == (404, 404)
    assert other_list.json() == []
    assert unknown.status_code == 404
    assert (await client.get(_documents_url(supplier.id), headers=manager)).json()[0]["id"] == document_id


async def test_deleting_removes_the_record_and_the_file_and_is_audited(
    client: AsyncClient,
    manager: dict[str, str],
    supplier: Supplier,
    db_session: AsyncSession,
    storage: LocalStorage,
) -> None:
    document_id = (await _upload(client, manager, supplier.id)).json()["id"]
    storage_key = await db_session.scalar(select(SupplierDocument.storage_key))
    assert storage_key is not None
    assert await storage.read(storage_key)

    response = await client.delete(f"{_documents_url(supplier.id)}/{document_id}", headers=manager)

    assert response.status_code == 204
    assert (await client.get(_documents_url(supplier.id), headers=manager)).json() == []
    with pytest.raises(StoredObjectNotFoundError):
        await storage.read(storage_key)
    actions = (
        (await db_session.execute(select(AuditLog.action).where(AuditLog.entity_type == "supplier"))).scalars().all()
    )
    assert {"supplier_document_uploaded", "supplier_document_removed"} <= set(actions)


async def test_the_expiring_list_spans_suppliers_and_leaves_out_what_is_fine(
    client: AsyncClient,
    manager: dict[str, str],
    supplier: Supplier,
    other_supplier: Supplier,
    today_is: Callable[[date], None],
    db_session: AsyncSession,
) -> None:
    await _upload(client, manager, supplier.id, document_type="w9", expiry_date=TODAY + timedelta(days=20))
    await _upload(client, manager, other_supplier.id, document_type="insurance", expiry_date=TODAY + timedelta(days=5))
    await _upload(
        client, manager, other_supplier.id, document_type="iso_certificate", expiry_date=TODAY - timedelta(days=3)
    )
    await _upload(client, manager, supplier.id, document_type="bank_letter", expiry_date=TODAY + timedelta(days=200))
    await _upload(client, manager, supplier.id, document_type="vat_certificate")
    url = f"{API}/supplier-documents/expiring"

    both = (await client.get(url, headers=manager)).json()
    soon = (await client.get(url, params={"status": "expiring_soon"}, headers=manager)).json()
    expired = (await client.get(url, params={"status": "expired"}, headers=manager)).json()
    await db_session.execute(update(Supplier).where(Supplier.id == other_supplier.id).values(is_active=False))
    await db_session.commit()
    active_only = (await client.get(url, headers=manager)).json()

    assert [(row["supplier_name"], row["document_type"], row["status"]) for row in both] == [
        ("Other Co", "iso_certificate", "expired"),
        ("Other Co", "insurance", "expiring_soon"),
        ("Test Supplier", "w9", "expiring_soon"),
    ]
    assert [row["document_type"] for row in soon] == ["insurance", "w9"]
    assert [row["document_type"] for row in expired] == ["iso_certificate"]
    assert [row["supplier_name"] for row in active_only] == ["Test Supplier"]


async def _notifications(db: AsyncSession) -> list[Notification]:
    return list((await db.execute(select(Notification).order_by(Notification.id))).scalars().all())


async def test_the_daily_job_notifies_supplier_managers_once_per_state(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    manager: dict[str, str],
    supplier: Supplier,
    today_is: Callable[[date], None],
    db_session: AsyncSession,
) -> None:
    await auth_headers("admin")
    await auth_headers("purchasing_officer")
    await auth_headers("finance")
    await _upload(client, manager, supplier.id, document_type="insurance", expiry_date=TODAY + timedelta(days=10))
    await _upload(client, manager, supplier.id, document_type="w9", expiry_date=TODAY + timedelta(days=100))

    first = await notify_expiring_supplier_documents(db_session, TODAY)
    again = await notify_expiring_supplier_documents(db_session, TODAY)

    sent = await _notifications(db_session)
    # Procurement manager and admin hold supplier:write; the officer and finance do not. One document needs attention.
    assert (first, again) == (2, 0)
    assert all("Supplier document expiring soon" in n.message and "Insurance certificate" in n.message for n in sent)
    assert "Test Supplier" in sent[0].message
    assert "2026-06-25" in sent[0].message


async def test_an_expired_document_is_announced_again_and_old_reminders_repeat(
    client: AsyncClient,
    manager: dict[str, str],
    supplier: Supplier,
    today_is: Callable[[date], None],
    db_session: AsyncSession,
) -> None:
    await _upload(client, manager, supplier.id, document_type="insurance", expiry_date=TODAY + timedelta(days=2))
    await notify_expiring_supplier_documents(db_session, TODAY)

    expired_today = await notify_expiring_supplier_documents(db_session, TODAY + timedelta(days=3))
    quiet = await notify_expiring_supplier_documents(db_session, TODAY + timedelta(days=4))
    week_later = datetime.now(UTC) + timedelta(days=8)
    repeated = await notify_expiring_supplier_documents(db_session, TODAY + timedelta(days=11), now=week_later)

    messages = [n.message for n in await _notifications(db_session)]
    assert (expired_today, quiet, repeated) == (1, 0, 1)
    assert messages[0].startswith("Supplier document expiring soon")
    assert messages[1].startswith("Supplier document expired")
    assert "expired on 2026-06-17" in messages[1]


async def test_the_daily_job_ignores_valid_documents_and_inactive_suppliers(
    client: AsyncClient,
    manager: dict[str, str],
    supplier: Supplier,
    other_supplier: Supplier,
    db_session: AsyncSession,
) -> None:
    await _upload(client, manager, supplier.id, expiry_date=TODAY + timedelta(days=90))
    await _upload(client, manager, other_supplier.id, expiry_date=TODAY - timedelta(days=1))
    await db_session.execute(update(Supplier).where(Supplier.id == other_supplier.id).values(is_active=False))
    await db_session.commit()

    assert await notify_expiring_supplier_documents(db_session, TODAY) == 0
