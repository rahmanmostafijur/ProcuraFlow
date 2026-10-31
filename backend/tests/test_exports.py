"""Accounting and record CSV exports: layouts, filters, formula-injection protection and permissions."""

import csv
import io
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_today
from app.models.audit import AuditLog
from app.models.product import Product
from app.models.supplier import Supplier
from app.services import export_common
from app.services.accounting_exports import QBO_HEADER, XERO_HEADER
from app.services.export_writer import CHUNK_ROWS, Fixed, csv_chunks, encode_cell
from tests.invoice_helpers import Staff, approved_invoice, matched_invoice, pay, received_po

EXPORTS = "/api/v1/exports"
QBO = f"{EXPORTS}/bills/quickbooks.csv"
XERO = f"{EXPORTS}/bills/xero.csv"


def _rows(response: Response) -> list[list[str]]:
    assert response.status_code == 200, response.text
    return list(csv.reader(io.StringIO(response.text)))


async def _bill(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, number: str, **extra: Any
) -> dict[str, Any]:
    po = await received_po(client, staff, supplier, product)
    return await approved_invoice(client, staff, po, product, number=number, **extra)


async def test_only_finance_and_admin_can_export(client: AsyncClient, staff: Staff) -> None:
    for url in (QBO, XERO, f"{EXPORTS}/purchase-orders.csv", f"{EXPORTS}/invoices.csv", f"{EXPORTS}/suppliers.csv"):
        assert (await client.get(url, headers=staff.finance)).status_code == 200
        assert (await client.get(url, headers=staff.admin)).status_code == 200
        for outsider in (staff.officer, staff.manager, staff.warehouse, staff.viewer):
            assert (await client.get(url, headers=outsider)).status_code == 403
        assert (await client.get(url)).status_code == 401


async def test_quickbooks_layout_has_one_row_per_bill_line(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    await _bill(client, staff, supplier, product, "INV-100", invoice_date="2026-03-05", due_date="2026-04-04")

    rows = _rows(await client.get(QBO, headers=staff.finance))

    assert tuple(rows[0]) == QBO_HEADER
    assert len(rows) == 2
    row = dict(zip(rows[0], rows[1], strict=True))
    assert row["*BillNo"] == "INV-100"
    assert row["*Vendor"] == "Test Supplier"
    assert (row["*BillDate"], row["*DueDate"]) == ("03/05/2026", "04/04/2026")
    assert row["Terms"] == "Net 30"
    assert row["*LineAmount"] == "100.00"
    assert row["LineTaxAmount"] == "0.00"
    assert row["Currency"] == "USD"
    assert row["Memo"].startswith("PO-")


async def test_xero_layout_uses_xero_columns_and_dates(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    await _bill(client, staff, supplier, product, "INV-200", invoice_date="2026-03-05", due_date="2026-04-04")

    rows = _rows(await client.get(XERO, headers=staff.finance))

    assert tuple(rows[0]) == XERO_HEADER
    row = dict(zip(rows[0], rows[1], strict=True))
    assert row["*ContactName"] == "Test Supplier"
    assert row["EmailAddress"] == "supplier@example.com"
    assert row["*InvoiceNumber"] == "INV-200"
    assert (row["*InvoiceDate"], row["*DueDate"]) == ("05/03/2026", "04/04/2026")
    assert (row["*Quantity"], row["*UnitAmount"]) == ("10", "10.00")
    assert row["*TaxType"] == "Tax Exempt"
    assert row["Description"] == "Test Widget"


async def test_bills_are_approved_and_paid_invoices_only(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    approved = await _bill(client, staff, supplier, product, "INV-APPROVED")
    paid = await _bill(client, staff, supplier, product, "INV-PAID")
    assert (await pay(client, staff.finance, paid["id"], paid["open_amount"])).status_code == 201
    unapproved_po = await received_po(client, staff, supplier, product)
    await matched_invoice(client, staff, unapproved_po, product, number="INV-MATCHED")

    everything = _rows(await client.get(QBO, headers=staff.finance))
    only_paid = _rows(await client.get(QBO, params={"status": "paid"}, headers=staff.finance))

    assert {row[0] for row in everything[1:]} == {approved["invoice_number"], "INV-PAID"}
    assert [row[0] for row in only_paid[1:]] == ["INV-PAID"]


async def test_a_status_that_is_not_a_bill_status_is_rejected(client: AsyncClient, staff: Staff) -> None:
    response = await client.get(QBO, params={"status": "draft"}, headers=staff.finance)

    assert response.status_code == 422
    assert "approved" in response.json()["detail"]


async def test_the_date_range_filters_on_the_invoice_date_inclusively(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    for number, day in (("INV-1", "2026-01-10"), ("INV-2", "2026-02-10"), ("INV-3", "2026-03-10")):
        await _bill(client, staff, supplier, product, number, invoice_date=day, due_date="2026-06-01")

    middle = _rows(
        await client.get(QBO, params={"date_from": "2026-02-10", "date_to": "2026-02-10"}, headers=staff.finance)
    )
    from_march = _rows(await client.get(QBO, params={"date_from": "2026-03-01"}, headers=staff.finance))
    backwards = await client.get(
        QBO, params={"date_from": "2026-03-01", "date_to": "2026-01-01"}, headers=staff.finance
    )

    assert [row[0] for row in middle[1:]] == ["INV-2"]
    assert [row[0] for row in from_march[1:]] == ["INV-3"]
    assert backwards.status_code == 422


async def test_an_empty_result_is_just_the_header(client: AsyncClient, staff: Staff) -> None:
    rows = _rows(await client.get(XERO, headers=staff.finance))

    assert rows == [list(XERO_HEADER)]


async def test_formula_characters_in_text_cells_are_neutralised(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, db_session: AsyncSession
) -> None:
    # The line description defaults to the product name, so name the product before the invoice is recorded.
    await db_session.execute(update(Product).values(name="@SUM(A1:A9)"))
    await db_session.commit()
    await _bill(client, staff, supplier, product, "-INV-9")
    await db_session.execute(update(Supplier).values(name='=HYPERLINK("http://evil.example","x")', email="+a@b.test"))
    await db_session.commit()

    qbo = _rows(await client.get(QBO, headers=staff.finance))
    xero = _rows(await client.get(XERO, headers=staff.finance))
    qbo_row = dict(zip(qbo[0], qbo[1], strict=True))
    xero_row = dict(zip(xero[0], xero[1], strict=True))

    assert qbo_row["*BillNo"] == "'-INV-9"
    assert qbo_row["*Vendor"].startswith("'=HYPERLINK")
    assert qbo_row["LineDescription"] == "'@SUM(A1:A9)"
    assert xero_row["*ContactName"].startswith("'=")
    assert xero_row["EmailAddress"] == "'+a@b.test"
    # Numbers are not text: they are written as they are, never prefixed.
    assert qbo_row["*LineAmount"] == "100.00"


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@", "\t", "\r"])
def test_every_formula_trigger_is_neutralised_in_text(prefix: str) -> None:
    assert encode_cell(f"{prefix}1+1") == f"'{prefix}1+1"


def test_numbers_dates_and_flags_are_formatted_not_neutralised() -> None:
    assert encode_cell(Fixed(Decimal("-5"))) == "-5.00"
    assert encode_cell(Fixed(Decimal("12.5"), 2)) == "12.50"
    assert encode_cell(Fixed(Decimal("0.005"), 2)) == "0.01"  # half up
    assert encode_cell(Fixed(Decimal("1000"), 0)) == "1000"
    assert encode_cell(Fixed(Decimal("12.3400"), 2, 4)) == "12.34"
    assert encode_cell(Fixed(Decimal("12.3456"), 2, 4)) == "12.3456"
    assert encode_cell(Fixed(Decimal("12.3450"), 2, 4)) == "12.345"
    assert encode_cell(-7) == "-7"
    assert (encode_cell(True), encode_cell(None)) == ("true", "")
    assert encode_cell(utc_today().replace(year=2026, month=1, day=2), "%d/%m/%Y") == "02/01/2026"


async def test_the_writer_emits_rows_in_chunks_and_always_the_header() -> None:
    async def rows(count: int) -> Any:
        for number in range(count):
            yield [f"row {number}", number]

    many = [chunk async for chunk in csv_chunks(["name", "n"], rows(CHUNK_ROWS * 2 + 1))]
    none = [chunk async for chunk in csv_chunks(["name", "n"], rows(0))]

    assert len(many) == 3
    assert many[0].startswith("name,n")
    assert "".join(many).count("\n") == CHUNK_ROWS * 2 + 2
    assert none == ["name,n\r\n"]


async def test_large_exports_are_read_in_pages(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, monkeypatch: pytest.MonkeyPatch
) -> None:
    for number in range(3):
        await _bill(client, staff, supplier, product, f"INV-P{number}")
    monkeypatch.setattr(export_common, "PAGE_SIZE", 1)

    rows = _rows(await client.get(QBO, headers=staff.finance))

    assert sorted(row[0] for row in rows[1:]) == ["INV-P0", "INV-P1", "INV-P2"]


async def test_an_export_is_audited(client: AsyncClient, staff: Staff, db_session: AsyncSession) -> None:
    await client.get(QBO, params={"date_from": "2026-01-01"}, headers=staff.finance)

    entry = await db_session.scalar(select(AuditLog).where(AuditLog.action == "export_downloaded"))

    assert entry is not None
    assert entry.extra_data is not None
    assert entry.extra_data["dataset"] == "quickbooks-bills"
    assert entry.extra_data["date_from"] == "2026-01-01"


async def test_purchase_order_export_filters_by_status_and_date(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    await received_po(client, staff, supplier, product)

    received = _rows(
        await client.get(f"{EXPORTS}/purchase-orders.csv", params={"status": "received"}, headers=staff.finance)
    )
    ordered = _rows(
        await client.get(f"{EXPORTS}/purchase-orders.csv", params={"status": "ordered"}, headers=staff.finance)
    )
    future = _rows(
        await client.get(
            f"{EXPORTS}/purchase-orders.csv",
            params={"date_from": (utc_today() + timedelta(days=1)).isoformat()},
            headers=staff.finance,
        )
    )
    bad = await client.get(f"{EXPORTS}/purchase-orders.csv", params={"status": "nonsense"}, headers=staff.finance)

    assert received[0][:3] == ["PO Number", "Supplier", "Status"]
    assert received[1][1:4] == ["Test Supplier", "received", "USD"]
    assert received[1][4:7] == ["100.00", "0.00", "100.00"]
    assert len(ordered) == 1
    assert len(future) == 1
    assert bad.status_code == 422


async def test_invoice_export_shows_paid_and_open_amounts(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    invoice = await _bill(client, staff, supplier, product, "INV-OPEN")
    assert (await pay(client, staff.finance, invoice["id"], "40.00")).status_code == 201

    rows = _rows(await client.get(f"{EXPORTS}/invoices.csv", headers=staff.finance))

    row = dict(zip(rows[0], rows[1], strict=True))
    assert (row["Invoice Number"], row["Total"], row["Paid"], row["Open"]) == ("INV-OPEN", "100.00", "40.00", "60.00")
    assert row["Status"] == "approved"


async def test_supplier_export_filters_active_and_neutralises_text(
    client: AsyncClient, staff: Staff, supplier: Supplier, db_session: AsyncSession
) -> None:
    db_session.add(Supplier(name="Gone Ltd", is_active=False))
    supplier.contact_name = "-2+3"
    await db_session.commit()

    everyone = _rows(await client.get(f"{EXPORTS}/suppliers.csv", headers=staff.finance))
    active = _rows(await client.get(f"{EXPORTS}/suppliers.csv", params={"status": "active"}, headers=staff.finance))
    inactive = _rows(await client.get(f"{EXPORTS}/suppliers.csv", params={"status": "inactive"}, headers=staff.finance))

    assert len(everyone) == 3
    assert [row[0] for row in active[1:]] == ["Test Supplier"]
    assert active[1][1] == "'-2+3"
    assert active[1][9] == "true"
    assert [row[0] for row in inactive[1:]] == ["Gone Ltd"]
