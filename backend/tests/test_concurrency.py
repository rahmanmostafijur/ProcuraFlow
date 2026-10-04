import asyncio
from collections.abc import Awaitable, Callable

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import InventoryTransactionType, POStatus
from app.models.inventory import InventoryTransaction
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.supplier import Supplier
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.user import User
from app.services import purchase_order_service as po_service
from app.services.inventory_service import apply_inventory_transaction, lock_products, record_opening_balance

# How long the second writer must stay blocked while the first one holds its row locks.
BLOCKED_WINDOW_SECONDS = 0.5
# Upper bound for any single concurrent operation, so a locking regression fails instead of hanging.
OPERATION_TIMEOUT_SECONDS = 10

ORDERED_QUANTITY = 10
PARALLEL_CREATIONS = 5

SessionWork = Callable[[AsyncSession], Awaitable[None]]


async def _create_po(db: AsyncSession, creator: User, product: Product, po_status: POStatus) -> PurchaseOrder:
    po = PurchaseOrder(
        po_number=f"PO-RACE-{po_status.value}",
        supplier_id=product.supplier_id,
        created_by=creator.id,
        status=po_status,
    )
    po.items = [PurchaseOrderItem(product_id=product.id, quantity=ORDERED_QUANTITY, unit_price=10)]
    db.add(po)
    await db.commit()
    return po


async def _run_in_session(factory: async_sessionmaker[AsyncSession], work: SessionWork) -> None:
    async with factory() as session:
        await work(session)
        await session.commit()


async def _race(factory: async_sessionmaker[AsyncSession], first: SessionWork, second: SessionWork) -> None:
    """Run `first` up to an uncommitted flush, start `second`, and require it to wait for `first`'s locks.

    Re-raises whatever `second` raised once `first` has committed.
    """
    async with factory() as first_session:
        await first(first_session)
        await first_session.flush()

        second_task = asyncio.create_task(_run_in_session(factory, second))
        try:
            done, _ = await asyncio.wait({second_task}, timeout=BLOCKED_WINDOW_SECONDS)
            assert not done, "second writer was not blocked by the first writer's row locks"

            await first_session.commit()
            await asyncio.wait_for(second_task, timeout=OPERATION_TIMEOUT_SECONDS)
        finally:
            if not second_task.done():
                second_task.cancel()
                await asyncio.gather(second_task, return_exceptions=True)


async def _stock_and_ledger_total(factory: async_sessionmaker[AsyncSession], product_id: int) -> tuple[int, int]:
    async with factory() as session:
        stock = await session.scalar(select(Product.current_stock).where(Product.id == product_id))
        ledger_total = await session.scalar(
            select(func.coalesce(func.sum(InventoryTransaction.quantity_delta), 0)).where(
                InventoryTransaction.product_id == product_id
            )
        )
        return stock, ledger_total


def _receive(po_id: int, product_id: int, quantity: int, user_id: int) -> SessionWork:
    async def work(session: AsyncSession) -> None:
        po = await po_service.get_purchase_order_for_update(session, po_id)
        await po_service.receive_purchase_order_items(session, po, {product_id: quantity}, user_id)

    return work


def _adjust(product_id: int, delta: int, user_id: int) -> SessionWork:
    async def work(session: AsyncSession) -> None:
        products = await lock_products(session, [product_id])
        await apply_inventory_transaction(
            session,
            product=products[product_id],
            quantity_delta=delta,
            transaction_type=InventoryTransactionType.ADJUSTMENT,
            created_by=user_id,
            reason="Concurrent count",
        )

    return work


def _open_balance(product_id: int, quantity: int, user_id: int) -> SessionWork:
    async def work(session: AsyncSession) -> None:
        await record_opening_balance(session, product_id=product_id, quantity=quantity, created_by=user_id)

    return work


def _transition(po_id: int, action: str, user: User) -> SessionWork:
    async def work(session: AsyncSession) -> None:
        po = await po_service.get_purchase_order_for_update(session, po_id)
        if action == "approve":
            po_service.approve_purchase_order(po, user)
        else:
            po_service.cancel_purchase_order(po)

    return work


async def test_concurrent_receipts_of_the_full_quantity_only_book_stock_once(
    session_factory, db_session, make_user, product
):
    user = await make_user("receiver@example.com", "warehouse_manager")
    po = await _create_po(db_session, user, product, POStatus.ORDERED)
    receive_all = _receive(po.id, product.id, ORDERED_QUANTITY, user.id)

    with pytest.raises(HTTPException) as rejected:
        await _race(session_factory, receive_all, receive_all)

    assert rejected.value.status_code == 409
    assert "status 'received'" in rejected.value.detail
    stock, ledger_total = await _stock_and_ledger_total(session_factory, product.id)
    assert stock == 50 + ORDERED_QUANTITY
    assert ledger_total == 50 + ORDERED_QUANTITY


async def test_concurrent_receipt_sees_the_quantity_already_received(
    session_factory, db_session, make_user, product
):
    user = await make_user("receiver@example.com", "warehouse_manager")
    po = await _create_po(db_session, user, product, POStatus.ORDERED)

    with pytest.raises(HTTPException) as rejected:
        await _race(
            session_factory,
            _receive(po.id, product.id, 6, user.id),
            _receive(po.id, product.id, ORDERED_QUANTITY, user.id),
        )

    assert rejected.value.status_code == 400
    assert "only 4 remain" in rejected.value.detail
    stock, ledger_total = await _stock_and_ledger_total(session_factory, product.id)
    assert stock == 56
    assert ledger_total == 50 + 6


async def test_concurrent_adjustments_cannot_drive_stock_negative(session_factory, make_user, product):
    user = await make_user("counter@example.com", "warehouse_manager")
    take_thirty = _adjust(product.id, -30, user.id)

    with pytest.raises(HTTPException) as rejected:
        await _race(session_factory, take_thirty, take_thirty)

    assert rejected.value.status_code == 409
    stock, ledger_total = await _stock_and_ledger_total(session_factory, product.id)
    assert stock == 20
    assert ledger_total == 50 - 30


async def test_concurrent_opening_balances_record_only_one(
    session_factory, db_session, make_user, supplier: Supplier, assert_stock_matches_ledger
):
    user = await make_user("stock-taker@example.com", "warehouse_manager")
    fresh = Product(sku="RACE-OB", name="Unstocked Widget", cost=1, supplier_id=supplier.id)
    db_session.add(fresh)
    await db_session.commit()

    with pytest.raises(HTTPException) as rejected:
        await _race(session_factory, _open_balance(fresh.id, 30, user.id), _open_balance(fresh.id, 30, user.id))

    assert rejected.value.status_code == 409
    stock, ledger_total = await _stock_and_ledger_total(session_factory, fresh.id)
    assert stock == 30
    assert ledger_total == 30
    await assert_stock_matches_ledger(fresh.id)


@pytest.mark.parametrize(
    ("first_action", "second_action", "expected_status"),
    [
        ("cancel", "approve", POStatus.CANCELLED),
        ("approve", "approve", POStatus.APPROVED),
    ],
)
async def test_concurrent_transitions_see_the_committed_status(
    session_factory, db_session, make_user, product, first_action, second_action, expected_status
):
    creator = await make_user("buyer@example.com", "procurement_manager")
    approver = await make_user("approver@example.com", "admin")
    po = await _create_po(db_session, creator, product, POStatus.SUBMITTED)

    with pytest.raises(HTTPException) as rejected:
        await _race(
            session_factory,
            _transition(po.id, first_action, approver),
            _transition(po.id, second_action, approver),
        )

    assert rejected.value.status_code == 409
    async with session_factory() as session:
        final = await session.get(PurchaseOrder, po.id)
        assert final.status == expected_status


async def test_parallel_receive_requests_accept_exactly_one(
    client: AsyncClient, auth_headers, session_factory, db_session, product
):
    headers = await auth_headers("warehouse_manager")
    creator = await db_session.scalar(select(User).where(User.email == "warehouse_manager@example.com"))
    po = await _create_po(db_session, creator, product, POStatus.ORDERED)
    payload = {"items": [{"product_id": product.id, "quantity": ORDERED_QUANTITY}]}

    responses = await asyncio.wait_for(
        asyncio.gather(
            *(
                client.post(f"/api/v1/purchase-orders/{po.id}/receive", json=payload, headers=headers)
                for _ in range(2)
            )
        ),
        timeout=OPERATION_TIMEOUT_SECONDS,
    )

    assert sorted(response.status_code for response in responses) == [200, 409]
    stock, ledger_total = await _stock_and_ledger_total(session_factory, product.id)
    assert stock == 50 + ORDERED_QUANTITY
    assert ledger_total == 50 + ORDERED_QUANTITY


async def test_parallel_purchase_order_creations_get_unique_numbers(
    client: AsyncClient, auth_headers, product
):
    headers = await auth_headers("procurement_manager")
    payload = {
        "supplier_id": product.supplier_id,
        "items": [{"product_id": product.id, "quantity": ORDERED_QUANTITY, "unit_price": "10.00"}],
    }

    responses = await asyncio.wait_for(
        asyncio.gather(
            *(
                client.post("/api/v1/purchase-orders", json=payload, headers=headers)
                for _ in range(PARALLEL_CREATIONS)
            )
        ),
        timeout=OPERATION_TIMEOUT_SECONDS,
    )

    assert [response.status_code for response in responses] == [201] * PARALLEL_CREATIONS
    po_numbers = {response.json()["po_number"] for response in responses}
    assert len(po_numbers) == PARALLEL_CREATIONS
