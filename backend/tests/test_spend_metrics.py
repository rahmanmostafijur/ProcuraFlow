from collections.abc import Callable
from datetime import date
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import COMMITTED_PO_STATUSES, POStatus
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.supplier import Supplier

# A distinct power-of-two total per status, so any wrongly included status changes the sum visibly.
LINE_TOTAL_BY_STATUS = {
    POStatus.DRAFT: Decimal("1.00"),
    POStatus.SUBMITTED: Decimal("2.00"),
    POStatus.APPROVED: Decimal("4.00"),
    POStatus.ORDERED: Decimal("8.00"),
    POStatus.PARTIALLY_RECEIVED: Decimal("16.00"),
    POStatus.RECEIVED: Decimal("32.00"),
    POStatus.CANCELLED: Decimal("64.00"),
}
COMMITTED_SPEND = Decimal("60.00")


async def _add_po_per_status(db: AsyncSession, product: Product, created_by: int) -> None:
    for po_status, line_total in LINE_TOTAL_BY_STATUS.items():
        po = PurchaseOrder(
            po_number=f"PO-SPEND-{po_status.value}",
            supplier_id=product.supplier_id,
            created_by=created_by,
            status=po_status,
        )
        po.items = [PurchaseOrderItem(product_id=product.id, quantity=1, unit_price=line_total)]
        db.add(po)
    await db.commit()


def test_committed_statuses_are_the_approved_rule() -> None:
    assert set(COMMITTED_PO_STATUSES) == {
        POStatus.APPROVED,
        POStatus.ORDERED,
        POStatus.PARTIALLY_RECEIVED,
        POStatus.RECEIVED,
    }


async def test_supplier_performance_counts_only_committed_orders(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: Callable,
    make_user: Callable,
    product: Product,
) -> None:
    headers = await auth_headers("viewer")
    creator = await make_user("creator@example.com", "procurement_manager")
    await _add_po_per_status(db_session, product, creator.id)

    response = await client.get("/api/v1/reports/supplier-performance", headers=headers)

    assert response.status_code == 200
    [row] = [r for r in response.json() if r["supplier_id"] == product.supplier_id]
    assert Decimal(str(row["total_spend"])) == COMMITTED_SPEND
    assert row["order_count"] == len(COMMITTED_PO_STATUSES)


async def test_supplier_performance_keeps_suppliers_without_committed_orders(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: Callable,
    make_user: Callable,
    product: Product,
) -> None:
    headers = await auth_headers("viewer")
    creator = await make_user("creator@example.com", "procurement_manager")
    idle_supplier = Supplier(name="Idle Supplier", email="idle@example.com")
    db_session.add(idle_supplier)
    await db_session.flush()
    for po_status in (POStatus.DRAFT, POStatus.SUBMITTED, POStatus.CANCELLED):
        po = PurchaseOrder(
            po_number=f"PO-IDLE-{po_status.value}",
            supplier_id=idle_supplier.id,
            created_by=creator.id,
            status=po_status,
        )
        po.items = [PurchaseOrderItem(product_id=product.id, quantity=3, unit_price=Decimal("5.00"))]
        db_session.add(po)
    await db_session.commit()

    response = await client.get("/api/v1/reports/supplier-performance", headers=headers)

    assert response.status_code == 200
    [row] = [r for r in response.json() if r["supplier_id"] == idle_supplier.id]
    assert Decimal(str(row["total_spend"])) == Decimal("0")
    assert row["order_count"] == 0


async def test_monthly_trend_counts_only_committed_orders(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: Callable,
    make_user: Callable,
    product: Product,
) -> None:
    headers = await auth_headers("viewer")
    creator = await make_user("creator@example.com", "procurement_manager")
    await _add_po_per_status(db_session, product, creator.id)

    response = await client.get("/api/v1/dashboard/monthly-trends", headers=headers)

    assert response.status_code == 200
    current_month = date.today().strftime("%Y-%m")
    [point] = [p for p in response.json() if p["month"] == current_month]
    assert Decimal(str(point["total_spend"])) == COMMITTED_SPEND
    assert point["order_count"] == len(COMMITTED_PO_STATUSES)


async def test_monthly_trend_omits_months_without_committed_orders(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: Callable,
    make_user: Callable,
    product: Product,
) -> None:
    headers = await auth_headers("viewer")
    creator = await make_user("creator@example.com", "procurement_manager")
    po = PurchaseOrder(
        po_number="PO-DRAFT-ONLY", supplier_id=product.supplier_id, created_by=creator.id, status=POStatus.DRAFT
    )
    po.items = [PurchaseOrderItem(product_id=product.id, quantity=2, unit_price=Decimal("9.00"))]
    db_session.add(po)
    await db_session.commit()

    response = await client.get("/api/v1/dashboard/monthly-trends", headers=headers)

    assert response.status_code == 200
    assert response.json() == []
