import os
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parents[1]
ENUM_TYPES_SQL = (
    "SELECT t.typname FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace "
    "WHERE n.nspname = 'public' AND t.typtype = 'e'"
)


def _alembic(database_url: str, *args: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": database_url},
        capture_output=True,
        text=True,
        timeout=180,
        check=False,  # the assertion below reports stdout and stderr on failure
    )
    assert result.returncode == 0, f"alembic {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}"
    return result.stdout


async def _admin(sql: str) -> None:
    server_url = make_url(get_settings().test_database_url).set(database="postgres")
    engine = create_async_engine(server_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    async with engine.connect() as connection:
        await connection.execute(text(sql))
    await engine.dispose()


async def _schema(database_url: str) -> tuple[set[str], list[str]]:
    engine = create_async_engine(database_url, poolclass=NullPool)
    async with engine.connect() as connection:
        tables = set(await connection.run_sync(lambda sync: inspect(sync).get_table_names()))
        enums = [row[0] for row in await connection.execute(text(ENUM_TYPES_SQL))]
    await engine.dispose()
    return tables, enums


@pytest.fixture
async def scratch_database_url() -> AsyncIterator[str]:
    name = f"pf_migrations_{uuid.uuid4().hex[:12]}"
    await _admin(f'CREATE DATABASE "{name}"')
    url = make_url(get_settings().test_database_url).set(database=name)
    try:
        yield url.render_as_string(hide_password=False)
    finally:
        await _admin(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def test_migration_history_has_a_single_head() -> None:
    output = _alembic(get_settings().test_database_url, "heads")

    assert output.count("(head)") == 1


async def test_migrations_round_trip_on_a_fresh_database(scratch_database_url: str) -> None:
    _alembic(scratch_database_url, "upgrade", "head")
    upgraded_tables, _ = await _schema(scratch_database_url)
    assert {"users", "purchase_orders", "refresh_tokens", "login_failures"} <= upgraded_tables

    _alembic(scratch_database_url, "downgrade", "base")
    downgraded_tables, leftover_enums = await _schema(scratch_database_url)
    assert downgraded_tables == {"alembic_version"}
    assert leftover_enums == []

    _alembic(scratch_database_url, "upgrade", "head")
    reupgraded_tables, _ = await _schema(scratch_database_url)
    assert reupgraded_tables == upgraded_tables


COMPANY_SETTINGS_REVISION = "d3a8f1c2b9e4"


async def _insert_legacy_orders(database_url: str) -> None:
    """Two orders as they existed before currencies and tax: one approved, one still a draft."""
    engine = create_async_engine(database_url, poolclass=NullPool)
    async with engine.begin() as connection:

        async def insert(sql: str, **params: object) -> int:
            return int((await connection.execute(text(sql), params)).scalar_one())

        role = await insert("INSERT INTO roles (name) VALUES ('legacy') RETURNING id")
        user = await insert(
            "INSERT INTO users (email, hashed_password, full_name, role_id, is_active) "
            "VALUES ('legacy@example.com', 'x', 'Legacy', :role, true) RETURNING id",
            role=role,
        )
        supplier = await insert("INSERT INTO suppliers (name, is_active) VALUES ('Legacy Supplier', true) RETURNING id")
        products = [
            await insert(
                "INSERT INTO products (sku, name, unit, cost, current_stock, minimum_stock, is_active) "
                "VALUES (:sku, :sku, 'unit', 1, 0, 0, true) RETURNING id",
                sku=sku,
            )
            for sku in ("LEG-1", "LEG-2")
        ]
        approved = await insert(
            "INSERT INTO purchase_orders (po_number, supplier_id, status, created_by) "
            "VALUES ('PO-LEGACY-1', :supplier, 'APPROVED', :user) RETURNING id",
            supplier=supplier,
            user=user,
        )
        draft = await insert(
            "INSERT INTO purchase_orders (po_number, supplier_id, status, created_by) "
            "VALUES ('PO-LEGACY-2', :supplier, 'DRAFT', :user) RETURNING id",
            supplier=supplier,
            user=user,
        )
        for po_id, product_id, quantity, price in (
            (approved, products[0], 4, "12.50"),
            (approved, products[1], 5, "10.00"),
            (draft, products[0], 2, "5.00"),
        ):
            await connection.execute(
                text(
                    "INSERT INTO purchase_order_items (po_id, product_id, quantity, unit_price, received_quantity) "
                    "VALUES (:po, :product, :quantity, :price, 0)"
                ),
                {"po": po_id, "product": product_id, "quantity": quantity, "price": price},
            )
    await engine.dispose()


async def test_currency_migration_keeps_existing_orders_worth_the_same(scratch_database_url: str) -> None:
    _alembic(scratch_database_url, "upgrade", COMPANY_SETTINGS_REVISION)
    await _insert_legacy_orders(scratch_database_url)

    _alembic(scratch_database_url, "upgrade", "head")

    engine = create_async_engine(scratch_database_url, poolclass=NullPool)
    async with engine.connect() as connection:
        orders = (
            await connection.execute(
                text(
                    "SELECT po_number, currency_code, subtotal, tax_total, grand_total, exchange_rate, "
                    "base_grand_total FROM purchase_orders ORDER BY po_number"
                )
            )
        ).all()
        lines = (
            await connection.execute(
                text(
                    "SELECT unit_price, line_net, line_tax, line_total, tax_percent "
                    "FROM purchase_order_items ORDER BY id"
                )
            )
        ).all()
        base_currency = (await connection.execute(text("SELECT base_currency_code FROM company_settings"))).scalar_one()
    await engine.dispose()

    approved, draft = orders
    assert base_currency == "USD"
    # The approved order is worth what its lines were worth, locked at rate 1 in the base currency.
    assert approved[:2] == ("PO-LEGACY-1", "USD")
    assert (approved[2], approved[3], approved[4]) == (Decimal(100), Decimal(0), Decimal(100))
    assert (approved[5], approved[6]) == (Decimal(1), Decimal(100))
    # The draft has a total but no locked rate yet; that happens at approval.
    assert draft[:2] == ("PO-LEGACY-2", "USD")
    assert draft[4] == Decimal(10)
    assert (draft[5], draft[6]) == (None, None)
    assert [tuple(line) for line in lines] == [
        (Decimal("12.5"), Decimal(50), Decimal(0), Decimal(50), Decimal(0)),
        (Decimal(10), Decimal(50), Decimal(0), Decimal(50), Decimal(0)),
        (Decimal(5), Decimal(10), Decimal(0), Decimal(10), Decimal(0)),
    ]


def _start_alembic(database_url: str, *args: str) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": database_url},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


async def test_several_instances_upgrading_at_once_all_succeed(scratch_database_url: str) -> None:
    """Instances that boot together each run `alembic upgrade head`; they must serialise, not collide."""
    processes = [_start_alembic(scratch_database_url, "upgrade", "head") for _ in range(3)]

    outcomes = [(process.communicate(timeout=240), process.returncode) for process in processes]

    failures = [(code, stderr[-400:]) for (_, stderr), code in outcomes if code != 0]
    assert not failures, failures
    tables, _ = await _schema(scratch_database_url)
    assert {"users", "refresh_tokens", "login_failures"} <= tables
    assert "(head)" in _alembic(scratch_database_url, "current")


APPROVALS_REVISION = "a8e0f2b4c6d3"
INVOICES_REVISION = "b7d1f3a5c9e2"


async def _insert_current_orders(database_url: str) -> None:
    """An ordered order with two lines, as it exists once currencies are in place."""
    await _execute(database_url, "INSERT INTO roles (name) VALUES ('legacy')")
    await _execute(
        database_url,
        "INSERT INTO users (email, hashed_password, full_name, role_id, is_active) "
        "SELECT 'legacy@example.com', 'x', 'Legacy', id, true FROM roles WHERE name = 'legacy'",
    )
    await _execute(database_url, "INSERT INTO suppliers (name, is_active) VALUES ('Legacy Supplier', true)")
    await _execute(
        database_url,
        "INSERT INTO products (sku, name, unit, cost, current_stock, minimum_stock, is_active) "
        "VALUES ('LEG-1', 'LEG-1', 'unit', 1, 0, 0, true), ('LEG-2', 'LEG-2', 'unit', 1, 0, 0, true)",
    )
    await _execute(
        database_url,
        "INSERT INTO purchase_orders (po_number, supplier_id, status, created_by, currency_code) "
        "SELECT 'PO-LEGACY-1', (SELECT min(id) FROM suppliers), 'ORDERED', (SELECT min(id) FROM users), 'USD'",
    )
    await _execute(
        database_url,
        "INSERT INTO purchase_order_items (po_id, product_id, quantity, unit_price, received_quantity) "
        "SELECT (SELECT min(id) FROM purchase_orders), id, 10, 5, 0 FROM products",
    )


async def _scalar(database_url: str, sql: str) -> object:
    engine = create_async_engine(database_url, poolclass=NullPool)
    async with engine.begin() as connection:
        value = (await connection.execute(text(sql))).scalar_one()
    await engine.dispose()
    return value


async def _execute(database_url: str, sql: str) -> None:
    engine = create_async_engine(database_url, poolclass=NullPool)
    async with engine.begin() as connection:
        await connection.execute(text(sql))
    await engine.dispose()


async def test_invoice_migration_keeps_legacy_orders_receipts_and_settings(scratch_database_url: str) -> None:
    _alembic(scratch_database_url, "upgrade", APPROVALS_REVISION)
    await _insert_current_orders(scratch_database_url)
    # A legacy order that was partly received before rejections existed, with a file attached to it.
    await _execute(
        scratch_database_url,
        "UPDATE purchase_order_items SET received_quantity = 3 WHERE id = (SELECT min(id) FROM purchase_order_items)",
    )
    await _execute(
        scratch_database_url,
        "INSERT INTO attachments (parent_type, parent_id, filename, content_type, size_bytes, sha256, storage_key, "
        "uploaded_by) SELECT 'PURCHASE_ORDER', min(id), 'legacy.pdf', 'application/pdf', 10, 'abc', 'legacy-key', "
        "(SELECT min(id) FROM users) FROM purchase_orders",
    )

    _alembic(scratch_database_url, "upgrade", "head")

    # Matching starts as three-way, and the tolerance and terms the company already had are untouched.
    assert await _scalar(scratch_database_url, "SELECT invoice_matching::text FROM company_settings") == "THREE_WAY"
    assert await _scalar(scratch_database_url, "SELECT invoice_tolerance_percent FROM company_settings") == Decimal(
        "2.00"
    )
    # Units received before are still counted as received (accepted), and the file is still attached.
    assert await _scalar(scratch_database_url, "SELECT min(received_quantity) FROM purchase_order_items") == 0
    assert await _scalar(scratch_database_url, "SELECT max(received_quantity) FROM purchase_order_items") == 3
    assert await _scalar(scratch_database_url, "SELECT count(*) FROM attachments WHERE filename = 'legacy.pdf'") == 1
    empty_count_sql = (
        "SELECT (SELECT count(*) FROM goods_receipts) + (SELECT count(*) FROM supplier_returns) "
        "+ (SELECT count(*) FROM supplier_invoices) + (SELECT count(*) FROM payments) "
        "+ (SELECT count(*) FROM payment_runs)"
    )
    assert await _scalar(scratch_database_url, empty_count_sql) == 0
    values = await _scalar(
        scratch_database_url,
        "SELECT string_agg(enumlabel, ',') FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
        "WHERE t.typname = 'attachment_parent_type'",
    )
    assert "SUPPLIER_INVOICE" in str(values)


async def test_the_invoice_migration_downgrades_even_with_invoice_attachments_and_upgrades_again(
    scratch_database_url: str,
) -> None:
    _alembic(scratch_database_url, "upgrade", "head")
    await _insert_current_orders(scratch_database_url)
    await _execute(
        scratch_database_url,
        "INSERT INTO attachments (parent_type, parent_id, filename, content_type, size_bytes, sha256, storage_key, "
        "uploaded_by) SELECT 'SUPPLIER_INVOICE', 1, 'bill.pdf', 'application/pdf', 10, 'abc', 'bill-key', "
        "(SELECT min(id) FROM users)",
    )

    _alembic(scratch_database_url, "downgrade", APPROVALS_REVISION)
    tables, _ = await _schema(scratch_database_url)
    assert "supplier_invoices" not in tables
    assert "payment_runs" not in tables
    assert await _scalar(scratch_database_url, "SELECT count(*) FROM attachments") == 0

    _alembic(scratch_database_url, "upgrade", "head")
    tables, _ = await _schema(scratch_database_url)
    assert {"supplier_invoices", "supplier_invoice_lines", "payments", "payment_runs", "payment_run_items"} <= tables
    assert await _scalar(scratch_database_url, "SELECT invoice_matching::text FROM company_settings") == "THREE_WAY"
