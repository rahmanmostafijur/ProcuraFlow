"""Bank files from released payment runs: SEPA for EUR, ACH for USD, generated once, audited, strictly validated."""

import asyncio
import hashlib
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.audit import AuditLog
from app.models.payment_file import PaymentRunFile
from app.models.product import Product
from app.models.supplier import Supplier
from app.services.sepa_file import NAMESPACE
from app.services.today import get_today
from app.storage.local import LocalStorage
from tests.invoice_helpers import RUNS, Staff
from tests.payment_file_helpers import (
    BRAZIL_IBAN,
    CHASE_ROUTING,
    FRENCH_IBAN,
    GERMAN_IBAN,
    OUR_IBAN,
    OUR_ROUTING,
    ach_details,
    approved_invoice_for,
    draft_run,
    released_run,
    second_supplier,
    sepa_details,
    set_bank_details,
    set_payer,
)

NS = {"p": NAMESPACE}
MONDAY = date(2026, 11, 2)


def _file_url(run_id: int, suffix: str = "") -> str:
    return f"{RUNS}/{run_id}/file{suffix}"


@pytest.fixture(autouse=True)
def monday() -> Iterator[None]:
    """Pin "today" to a Monday so the value date (next business day) is predictable."""
    app.dependency_overrides[get_today] = lambda: MONDAY
    yield
    app.dependency_overrides.pop(get_today, None)


async def _sepa_run(
    client: AsyncClient,
    staff: Staff,
    supplier: Supplier,
    product: Product,
    numbers: tuple[str, ...] = ("INV-1", "INV-2"),
) -> dict[str, Any]:
    await set_payer(client, staff)
    await set_bank_details(client, staff, supplier.id, sepa_details())
    invoices = [await approved_invoice_for(client, staff, supplier, product, n, currency="EUR") for n in numbers]
    return await released_run(client, staff, [invoice["id"] for invoice in invoices])


async def _ach_run(
    client: AsyncClient,
    staff: Staff,
    supplier: Supplier,
    product: Product,
    numbers: tuple[str, ...] = ("INV-1", "INV-2"),
) -> dict[str, Any]:
    await set_payer(client, staff)
    await set_bank_details(client, staff, supplier.id, ach_details())
    invoices = [await approved_invoice_for(client, staff, supplier, product, n) for n in numbers]
    return await released_run(client, staff, [invoice["id"] for invoice in invoices])


async def test_a_sepa_file_is_built_from_a_released_euro_run(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    run = await _sepa_run(client, staff, supplier, product)

    created = await client.post(_file_url(run["id"]), headers=staff.finance)
    download = await client.get(_file_url(run["id"], "/download"), headers=staff.finance)

    assert created.status_code == 201
    info = created.json()
    assert (info["file_format"], info["currency_code"], info["transaction_count"]) == ("sepa_pain001", "EUR", 2)
    assert info["filename"] == f"{run['number']}-sepa.xml"
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("application/xml")
    assert download.headers["x-content-type-options"] == "nosniff"
    root = ET.fromstring(download.content)  # noqa: S314 - the app's own file
    header = root.find("p:CstmrCdtTrfInitn/p:GrpHdr", NS)
    batch = root.find("p:CstmrCdtTrfInitn/p:PmtInf", NS)
    assert header is not None
    assert batch is not None
    transactions = batch.findall("p:CdtTrfTxInf", NS)
    amounts = [Decimal(t.findtext("p:Amt/p:InstdAmt", namespaces=NS) or "0") for t in transactions]
    assert len(transactions) == 2 == int(header.findtext("p:NbOfTxs", namespaces=NS) or 0)
    assert (
        str(sum(amounts)) == header.findtext("p:CtrlSum", namespaces=NS) == batch.findtext("p:CtrlSum", namespaces=NS)
    )
    assert Decimal(header.findtext("p:CtrlSum", namespaces=NS) or "0") == Decimal(str(run["total"]))
    assert {t.findtext("p:CdtrAcct/p:Id/p:IBAN", namespaces=NS) for t in transactions} == {GERMAN_IBAN}
    assert batch.findtext("p:DbtrAcct/p:Id/p:IBAN", namespaces=NS) == OUR_IBAN
    assert {t.findtext("p:PmtId/p:EndToEndId", namespaces=NS) for t in transactions} == {"INV-1", "INV-2"}
    assert batch.findtext("p:ReqdExctnDt", namespaces=NS) == "2026-11-03"
    assert header.findtext("p:MsgId", namespaces=NS) == run["number"]


async def test_an_ach_file_has_valid_records_totals_and_padding(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    run = await _ach_run(client, staff, supplier, product)

    created = await client.post(_file_url(run["id"]), headers=staff.finance)
    download = await client.get(_file_url(run["id"], "/download"), headers=staff.finance)

    assert created.status_code == 201
    assert created.json()["file_format"] == "nacha_ach"
    assert created.json()["filename"].endswith("-ach.txt")
    records = download.content.decode("ascii").split("\r\n")[:-1]
    assert all(len(record) == 94 for record in records)
    assert len(records) % 10 == 0
    assert [record[0] for record in records[:5]] == ["1", "5", "6", "6", "8"]
    assert records[5][0] == "9"
    assert all(set(record) == {"9"} for record in records[6:])
    entries = records[2:4]
    cents = [int(entry[29:39]) for entry in entries]
    assert cents == [10000, 10000]
    assert [entry[3:12] for entry in entries] == [CHASE_ROUTING] * 2
    assert {entry[12:29].strip() for entry in entries} == {"000123456789"}
    assert {entry[39:54].strip() for entry in entries} == {"INV-1", "INV-2"}
    batch_control, file_control = records[4], records[5]
    entry_hash = (int(CHASE_ROUTING[:8]) * 2) % 10**10
    assert int(batch_control[10:20]) == int(file_control[21:31]) == entry_hash
    assert int(batch_control[32:44]) == int(file_control[43:55]) == sum(cents)
    assert Decimal(sum(cents)) / 100 == Decimal(str(run["total"]))
    assert batch_control[79:87] == OUR_ROUTING[:8]
    assert records[0][3:13] == " " + OUR_ROUTING
    assert records[1][69:75] == "261103"


async def test_the_file_is_generated_once_and_downloads_return_the_same_bytes(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, db_session: AsyncSession
) -> None:
    run = await _sepa_run(client, staff, supplier, product)
    first = await client.post(_file_url(run["id"]), headers=staff.finance)
    first_bytes = (await client.get(_file_url(run["id"], "/download"), headers=staff.finance)).content
    # The supplier changes bank, and a day passes: the file the bank already has must not change.
    await set_bank_details(client, staff, supplier.id, sepa_details(FRENCH_IBAN, "FR", "Dupont SARL"))
    app.dependency_overrides[get_today] = lambda: MONDAY + timedelta(days=3)

    again = await client.post(_file_url(run["id"]), headers=staff.finance)
    second_bytes = (await client.get(_file_url(run["id"], "/download"), headers=staff.finance)).content
    info = await client.get(_file_url(run["id"]), headers=staff.finance)

    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json() == first.json() == info.json()
    assert first_bytes == second_bytes
    assert GERMAN_IBAN.encode() in second_bytes
    assert FRENCH_IBAN.encode() not in second_bytes
    assert await db_session.scalar(select(func.count()).select_from(PaymentRunFile)) == 1


async def test_the_stored_hash_matches_the_downloaded_bytes(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    run = await _ach_run(client, staff, supplier, product)
    info = (await client.post(_file_url(run["id"]), headers=staff.finance)).json()

    data = (await client.get(_file_url(run["id"], "/download"), headers=staff.finance)).content

    assert hashlib.sha256(data).hexdigest() == info["sha256"]
    assert len(data) == info["size_bytes"]


async def test_generation_and_each_download_are_audited(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, db_session: AsyncSession
) -> None:
    run = await _sepa_run(client, staff, supplier, product)
    await client.post(_file_url(run["id"]), headers=staff.finance)
    await client.post(_file_url(run["id"]), headers=staff.finance)
    for _ in range(2):
        await client.get(_file_url(run["id"], "/download"), headers=staff.finance)

    actions = (
        (
            await db_session.execute(
                select(AuditLog.action).where(AuditLog.action.like("payment_file_%")).order_by(AuditLog.id)
            )
        )
        .scalars()
        .all()
    )

    assert actions == ["payment_file_generated", "payment_file_downloaded", "payment_file_downloaded"]


async def test_concurrent_exports_create_one_file(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, db_session: AsyncSession
) -> None:
    run = await _sepa_run(client, staff, supplier, product)

    responses = await asyncio.gather(*(client.post(_file_url(run["id"]), headers=staff.finance) for _ in range(4)))

    assert sorted(response.status_code for response in responses) == [200, 200, 200, 201]
    assert len({response.json()["sha256"] for response in responses}) == 1
    assert await db_session.scalar(select(func.count()).select_from(PaymentRunFile)) == 1


async def test_a_run_that_is_not_released_cannot_be_exported(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    await set_payer(client, staff)
    await set_bank_details(client, staff, supplier.id, ach_details())
    invoice = await approved_invoice_for(client, staff, supplier, product, "INV-1")
    draft = await draft_run(client, staff, [invoice["id"]])

    response = await client.post(_file_url(draft["id"]), headers=staff.finance)
    downloaded = await client.get(_file_url(draft["id"], "/download"), headers=staff.finance)
    await client.post(f"{RUNS}/{draft['id']}/cancel", headers=staff.finance)
    after_cancel = await client.post(_file_url(draft["id"]), headers=staff.finance)

    assert response.status_code == 409
    assert "released" in response.json()["detail"]
    assert downloaded.status_code == 404
    assert after_cancel.status_code == 409


async def test_a_supplier_without_bank_details_is_listed_and_nothing_is_stored(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, db_session: AsyncSession
) -> None:
    other, other_product = await second_supplier(db_session)
    await set_payer(client, staff)
    await set_bank_details(client, staff, supplier.id, sepa_details())
    good = await approved_invoice_for(client, staff, supplier, product, "INV-GOOD", currency="EUR")
    bad = await approved_invoice_for(client, staff, other, other_product, "INV-NOBANK", currency="EUR")
    run = await released_run(client, staff, [good["id"], bad["id"]])

    response = await client.post(_file_url(run["id"]), headers=staff.finance)
    info = await client.get(_file_url(run["id"]), headers=staff.finance)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "Second Supplier (invoice INV-NOBANK): no approved bank details" in detail
    assert "INV-GOOD" not in detail
    assert info.status_code == 404
    assert await db_session.scalar(select(func.count()).select_from(PaymentRunFile)) == 0


async def test_each_format_names_what_is_missing(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, db_session: AsyncSession
) -> None:
    await set_payer(client, staff)
    # An IBAN-only supplier cannot be paid by ACH; a US account cannot be paid by SEPA.
    await set_bank_details(client, staff, supplier.id, sepa_details())
    usd = await approved_invoice_for(client, staff, supplier, product, "INV-USD")
    usd_run = await released_run(client, staff, [usd["id"]])
    other, other_product = await second_supplier(db_session)
    await set_bank_details(client, staff, other.id, ach_details())
    eur = await approved_invoice_for(client, staff, other, other_product, "INV-EUR", currency="EUR")
    eur_run = await released_run(client, staff, [eur["id"]])

    ach = await client.post(_file_url(usd_run["id"]), headers=staff.finance)
    sepa = await client.post(_file_url(eur_run["id"]), headers=staff.finance)

    assert ach.status_code == sepa.status_code == 422
    assert "missing routing number" in ach.json()["detail"]
    assert "missing bank account number" in ach.json()["detail"]
    assert "is not US" in ach.json()["detail"]
    assert "missing IBAN" in sepa.json()["detail"]
    assert "outside the SEPA area" in sepa.json()["detail"]


async def test_a_bank_outside_the_sepa_area_is_refused(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    await set_payer(client, staff)
    await set_bank_details(client, staff, supplier.id, sepa_details(BRAZIL_IBAN, "BR", "Fornecedor Ltda"))
    invoice = await approved_invoice_for(client, staff, supplier, product, "INV-BR", currency="EUR")
    run = await released_run(client, staff, [invoice["id"]])

    response = await client.post(_file_url(run["id"]), headers=staff.finance)

    assert response.status_code == 422
    assert "bank country BR is outside the SEPA area" in response.json()["detail"]


async def test_the_company_account_must_be_set_for_the_format(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    await set_bank_details(client, staff, supplier.id, ach_details())
    invoice = await approved_invoice_for(client, staff, supplier, product, "INV-1")
    run = await released_run(client, staff, [invoice["id"]])

    refused = await client.post(_file_url(run["id"]), headers=staff.finance)
    await set_payer(client, staff)
    allowed = await client.post(_file_url(run["id"]), headers=staff.finance)

    assert refused.status_code == 422
    assert "payer routing number" in refused.json()["detail"]
    assert "ACH company ID" in refused.json()["detail"]
    assert allowed.status_code == 201


async def test_a_currency_without_a_bank_file_format_is_refused(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    await set_payer(client, staff)
    await set_bank_details(client, staff, supplier.id, sepa_details())
    invoice = await approved_invoice_for(client, staff, supplier, product, "INV-GBP", currency="GBP")
    run = await released_run(client, staff, [invoice["id"]])

    response = await client.post(_file_url(run["id"]), headers=staff.finance)

    assert response.status_code == 422
    assert "GBP" in response.json()["detail"]


async def test_only_finance_and_admin_can_export_and_unknown_runs_are_404(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    run = await _ach_run(client, staff, supplier, product)
    url = _file_url(run["id"])

    for outsider in (staff.officer, staff.manager, staff.warehouse, staff.viewer):
        assert (await client.post(url, headers=outsider)).status_code == 403
        assert (await client.get(url, headers=outsider)).status_code == 403
        assert (await client.get(f"{url}/download", headers=outsider)).status_code == 403
    assert (await client.post(url)).status_code == 401
    assert (await client.post(url, headers=staff.admin)).status_code == 201
    assert (await client.post(_file_url(9999), headers=staff.finance)).status_code == 404
    assert (await client.get(_file_url(9999), headers=staff.finance)).status_code == 404


async def test_a_tampered_stored_file_is_not_served(
    client: AsyncClient,
    staff: Staff,
    supplier: Supplier,
    product: Product,
    db_session: AsyncSession,
    storage: LocalStorage,
) -> None:
    run = await _ach_run(client, staff, supplier, product)
    await client.post(_file_url(run["id"]), headers=staff.finance)
    key = await db_session.scalar(select(PaymentRunFile.storage_key))
    assert key is not None
    await storage.save(key, b"1" + b" " * 93, "text/plain")

    response = await client.get(_file_url(run["id"], "/download"), headers=staff.finance)

    assert response.status_code == 500
    assert "integrity" in response.json()["detail"]
