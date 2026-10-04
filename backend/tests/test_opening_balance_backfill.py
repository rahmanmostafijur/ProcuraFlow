import importlib.util
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import InventoryTransactionType
from app.models.inventory import InventoryTransaction
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User

VERSIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"
MIGRATION_PATH = VERSIONS_DIR / "1224b37f7c19_backfill_opening_balance_ledger_rows.py"
BACKFILL_REASON = "Backfilled opening balance (migration 1224b37f7c19)"


def _load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("backfill_opening_balance_migration", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _run_migration(factory: async_sessionmaker[AsyncSession], step: str) -> None:
    migration = _load_migration()

    def _apply(sync_session) -> None:
        with Operations.context(MigrationContext.configure(sync_session.connection())):
            getattr(migration, step)()

    async with factory() as session:
        await session.run_sync(_apply)
        await session.commit()


async def _add_product(db: AsyncSession, supplier: Supplier, sku: str, stock: int) -> Product:
    # Written straight to the table, the way stock was set before it went through the ledger.
    product = Product(sku=sku, name=sku, cost=1, current_stock=stock, supplier_id=supplier.id)
    db.add(product)
    await db.flush()
    return product


def _movement(product: Product, kind: InventoryTransactionType, delta: int, stock: int, user: User):
    return InventoryTransaction(
        product_id=product.id, type=kind, quantity_delta=delta, resulting_stock=stock, created_by=user.id
    )


async def _ledger(factory: async_sessionmaker[AsyncSession]) -> list[tuple]:
    async with factory() as session:
        rows = await session.execute(
            select(
                InventoryTransaction.product_id,
                InventoryTransaction.type,
                InventoryTransaction.quantity_delta,
                InventoryTransaction.resulting_stock,
                InventoryTransaction.reason,
                InventoryTransaction.created_by,
            ).order_by(InventoryTransaction.id)
        )
        return [tuple(row) for row in rows]


@pytest.fixture
def legacy_stock(db_session: AsyncSession, supplier: Supplier, make_user: Callable):
    """Products whose stock was set directly, with no, partial, excess or matching ledger history."""

    async def _create() -> dict:
        clerk = await make_user("clerk@example.com", "warehouse_manager")
        no_history = await _add_product(db_session, supplier, "LEG-NONE", 30)
        partial = await _add_product(db_session, supplier, "LEG-PARTIAL", 50)
        excess = await _add_product(db_session, supplier, "LEG-EXCESS", 5)
        matching = await _add_product(db_session, supplier, "LEG-MATCH", 40)
        empty = await _add_product(db_session, supplier, "LEG-EMPTY", 0)
        db_session.add_all(
            [
                _movement(partial, InventoryTransactionType.PO_RECEIPT, 20, 20, clerk),
                _movement(excess, InventoryTransactionType.ADJUSTMENT, 10, 10, clerk),
                _movement(matching, InventoryTransactionType.OPENING_BALANCE, 40, 40, clerk),
            ]
        )
        await db_session.commit()
        return {
            "clerk": clerk,
            "no_history": no_history,
            "partial": partial,
            "excess": excess,
            "matching": matching,
            "empty": empty,
        }

    return _create


async def test_backfill_reconciles_stock_with_the_ledger(
    session_factory, db_session: AsyncSession, make_user: Callable, legacy_stock, assert_stock_matches_ledger
):
    data = await legacy_stock()
    retired_admin = await make_user("retired-admin@example.com", "admin")
    retired_admin.is_active = False
    await db_session.commit()
    first_admin = await make_user("first-admin@example.com", "admin")
    await make_user("second-admin@example.com", "admin")
    ledger_before = await _ledger(session_factory)

    await _run_migration(session_factory, "upgrade")

    ledger_after = await _ledger(session_factory)
    assert ledger_after[: len(ledger_before)] == ledger_before
    opening = InventoryTransactionType.OPENING_BALANCE
    assert sorted(ledger_after[len(ledger_before) :]) == sorted(
        [
            (data["no_history"].id, opening, 30, 30, BACKFILL_REASON, first_admin.id),
            (data["partial"].id, opening, 30, 50, BACKFILL_REASON, first_admin.id),
            (data["excess"].id, opening, -5, 5, BACKFILL_REASON, first_admin.id),
        ]
    )
    for key in ("no_history", "partial", "excess", "matching", "empty"):
        await assert_stock_matches_ledger(data[key].id)

    await _run_migration(session_factory, "upgrade")
    assert await _ledger(session_factory) == ledger_after


async def test_backfill_downgrade_removes_only_the_backfilled_rows(
    session_factory, make_user: Callable, legacy_stock
):
    await legacy_stock()
    await make_user("first-admin@example.com", "admin")
    ledger_before = await _ledger(session_factory)
    await _run_migration(session_factory, "upgrade")

    await _run_migration(session_factory, "downgrade")

    assert await _ledger(session_factory) == ledger_before


async def test_backfill_fails_clearly_without_an_active_admin(session_factory, legacy_stock):
    await legacy_stock()
    ledger_before = await _ledger(session_factory)

    with pytest.raises(RuntimeError, match="no active admin user"):
        await _run_migration(session_factory, "upgrade")

    assert await _ledger(session_factory) == ledger_before


async def test_backfill_without_mismatches_needs_no_admin(session_factory, product):
    ledger_before = await _ledger(session_factory)

    await _run_migration(session_factory, "upgrade")

    assert await _ledger(session_factory) == ledger_before
