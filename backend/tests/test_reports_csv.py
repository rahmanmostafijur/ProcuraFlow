import csv
import io

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.csv_safety import neutralize_formula
from app.models.product import Product
from app.models.supplier import Supplier

CSV_URL = "/api/v1/reports/inventory-status.csv"


def _rows(response) -> list[list[str]]:
    return list(csv.reader(io.StringIO(response.text)))


@pytest.mark.parametrize(
    "value, expected",
    [
        ("Plain name", "Plain name"),
        ("A4 Paper - 80gsm", "A4 Paper - 80gsm"),
        ("=1+1", "'=1+1"),
        ("+SUM(A1:A2)", "'+SUM(A1:A2)"),
        ("-2+3", "'-2+3"),
        ("@cmd", "'@cmd"),
        ('=HYPERLINK("http://evil.example","x")', "'=HYPERLINK(\"http://evil.example\",\"x\")"),
        ("\tTabbed", "'\tTabbed"),
        ("\rReturn", "'\rReturn"),
        ("", ""),
    ],
)
def test_neutralize_formula_defuses_spreadsheet_formulas(value: str, expected: str) -> None:
    assert neutralize_formula(value) == expected


async def test_inventory_csv_requires_authentication(client: AsyncClient):
    response = await client.get(CSV_URL)

    assert response.status_code == 401


async def test_inventory_csv_lists_products_for_a_signed_in_user(
    client: AsyncClient, auth_headers, product: Product
):
    headers = await auth_headers("viewer")

    response = await client.get(CSV_URL, headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    header, *rows = _rows(response)
    assert header[:3] == ["SKU", "Name", "Current Stock"]
    assert rows == [["TEST-001", "Test Widget", "50", "10", "10.00", "500.00", "False"]]


async def test_inventory_csv_does_not_emit_live_formulas_from_product_names(
    client: AsyncClient, auth_headers, db_session: AsyncSession, supplier: Supplier
):
    db_session.add(
        Product(
            sku="=CMD|' /C calc'!A0",
            name='=HYPERLINK("http://evil.example","click")',
            cost=1,
            minimum_stock=0,
            supplier_id=supplier.id,
        )
    )
    await db_session.commit()
    headers = await auth_headers("viewer")

    response = await client.get(CSV_URL, headers=headers)

    _, row = _rows(response)
    assert row[0].startswith("'=")
    assert row[1].startswith("'=")
