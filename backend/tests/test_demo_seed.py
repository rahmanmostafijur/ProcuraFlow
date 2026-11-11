"""The demo seed and its reset: counts, internal consistency and idempotency, using a real (empty) database."""

from collections import Counter
from collections.abc import AsyncIterator
from datetime import date, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.clock import utc_today
from app.core.config import Settings, get_settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.demo.accounts import ACCOUNTS_BY_KEY, DEMO_ACCOUNTS
from app.demo.plan import build_order_plans
from app.demo.reset import DemoResetRefusedError, reset_demo
from app.demo.seed import DemoSeedSummary, seed_demo
from app.main import app
from app.models.approval import ApprovalStep
from app.models.enums import InvoiceStatus, POStatus
from app.models.goods_receipt import GoodsReceiptLine, SupplierReturn
from app.models.inventory import InventoryTransaction
from app.models.payment import Payment, PaymentRun
from app.models.po_version import PurchaseOrderVersion
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.role import Role
from app.models.supplier import Supplier
from app.models.supplier_document import SupplierDocument
from app.models.supplier_invoice import SupplierInvoice
from app.models.user import User

API = "/api/v1"
MIN_MONTHS_SPANNED = 11


@pytest.fixture
def demo_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    settings = get_settings()
    monkeypatch.setattr(settings, "demo_mode", True)
    return settings


@pytest_asyncio.fixture
async def demo_db() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """A pooled connection source for the application and the seed: the seed makes hundreds of requests and the
    per-test connection-per-session engine of the other tests would make it needlessly slow."""
    engine = create_async_engine(get_settings().test_database_url, pool_size=4)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    previous = app.dependency_overrides[get_db]

    async def _get_db() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    yield factory
    app.dependency_overrides[get_db] = previous
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded(
    demo_settings: Settings, demo_db: async_sessionmaker[AsyncSession]
) -> tuple[DemoSeedSummary, async_sessionmaker[AsyncSession]]:
    return await seed_demo(demo_settings, demo_db), demo_db


def _finance_headers(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user_id), 'finance')}"}


async def _scalar_count(db: AsyncSession, statement: object) -> int:
    return int(await db.scalar(statement) or 0)  # type: ignore[call-overload]


async def test_the_seed_creates_the_documented_company(
    seeded: tuple[DemoSeedSummary, async_sessionmaker[AsyncSession]],
) -> None:
    summary, factory = seeded

    async with factory() as db:
        users = {user.email: user for user in (await db.scalars(select(User))).all()}
        roles = {role.id: role.name for role in (await db.scalars(select(Role))).all()}
        suppliers = (await db.scalars(select(Supplier))).all()
        orders = (await db.scalars(select(PurchaseOrder))).all()

    assert summary.users == len(DEMO_ACCOUNTS) == len(users)
    for account in DEMO_ACCOUNTS:
        user = users[account.email]
        assert roles[user.role_id] == account.role_name
        assert (user.supplier_id is not None) is account.is_portal
    assert len(suppliers) == 8
    assert {order.currency_code for order in orders} == {"USD", "EUR", "GBP"}
    assert len(orders) >= 36
    assert {order.status for order in orders} >= {
        POStatus.DRAFT,
        POStatus.SUBMITTED,
        POStatus.ORDERED,
        POStatus.PARTIALLY_RECEIVED,
        POStatus.RECEIVED,
    }
    months = {order.created_at.strftime("%Y-%m") for order in orders}
    assert len(months) >= MIN_MONTHS_SPANNED
    assert min(order.created_at for order in orders).date() < utc_today() - timedelta(days=300)


async def test_every_money_total_agrees(seeded: tuple[DemoSeedSummary, async_sessionmaker[AsyncSession]]) -> None:
    _, factory = seeded

    async with factory() as db:
        orders = (await db.scalars(select(PurchaseOrder))).all()
        invoices = (await db.scalars(select(SupplierInvoice))).all()
        paid_by_invoice = {
            invoice_id: total
            for invoice_id, total in (
                await db.execute(select(Payment.invoice_id, func.sum(Payment.amount)).group_by(Payment.invoice_id))
            ).all()
        }
        run = (await db.scalars(select(PaymentRun))).one()
        run_payments = (await db.scalars(select(Payment).where(Payment.payment_run_id == run.id))).all()

    assert all(order.subtotal + order.tax_total == order.grand_total for order in orders)
    assert all(invoice.subtotal + invoice.tax_total == invoice.grand_total for invoice in invoices)
    for invoice in invoices:
        paid = paid_by_invoice.get(invoice.id, Decimal(0))
        if invoice.status == InvoiceStatus.PAID:
            assert paid == invoice.grand_total, invoice.invoice_number
        else:
            assert paid < invoice.grand_total, invoice.invoice_number
    assert run.status.value == "released"
    assert run.currency_code == "EUR"
    assert sum(payment.amount for payment in run_payments) == run.total
    assert len(run_payments) == 2


async def test_stock_agrees_with_the_ledger_and_some_products_are_low(
    seeded: tuple[DemoSeedSummary, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = seeded

    async with factory() as db:
        products = (await db.scalars(select(Product))).all()
        rows = await db.execute(
            select(InventoryTransaction.product_id, func.sum(InventoryTransaction.quantity_delta)).group_by(
                InventoryTransaction.product_id
            )
        )
        ledger = {product_id: total for product_id, total in rows.all()}

    assert len(products) == 24
    assert all(product.current_stock == ledger[product.id] for product in products)
    assert any(product.current_stock < product.minimum_stock for product in products)


async def test_the_scenarios_the_demo_promises_are_all_present(
    seeded: tuple[DemoSeedSummary, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = seeded
    today = utc_today()

    async with factory() as db:
        highest_version = await db.scalar(select(func.max(PurchaseOrderVersion.version)))
        rejected_units = await db.scalar(select(func.sum(GoodsReceiptLine.rejected_quantity)))
        returns = (await db.scalars(select(SupplierReturn))).all()
        delegated = await _scalar_count(
            db, select(func.count()).select_from(ApprovalStep).where(ApprovalStep.on_behalf_of.is_not(None))
        )
        documents = (await db.scalars(select(SupplierDocument))).all()
        invoices = (await db.scalars(select(SupplierInvoice))).all()
        portal_suppliers = await _scalar_count(
            db, select(func.count(func.distinct(User.supplier_id))).where(User.supplier_id.is_not(None))
        )

    reasons = Counter(reason["code"] for invoice in invoices for reason in invoice.exception_reasons or [])
    assert highest_version == 3  # the original and two amendments
    assert (rejected_units, [row.quantity for row in returns]) == (2, [2])
    assert delegated == 1
    assert reasons["DUPLICATE_INVOICE"] == 1
    assert [invoice for invoice in invoices if invoice.status == InvoiceStatus.EXCEPTION]
    assert [document for document in documents if document.expiry_date and document.expiry_date < today]
    assert [
        document
        for document in documents
        if document.expiry_date and today <= document.expiry_date <= today + timedelta(days=30)
    ]
    assert portal_suppliers == 2


async def test_budgets_show_healthy_near_limit_and_over_limit_centres(
    seeded: tuple[DemoSeedSummary, async_sessionmaker[AsyncSession]], client: AsyncClient
) -> None:
    _, factory = seeded
    async with factory() as db:
        finance_id = await db.scalar(select(User.id).where(User.email == ACCOUNTS_BY_KEY["finance"].email))

    response = await client.get(f"{API}/budgets", headers=_finance_headers(int(finance_id or 0)))

    health = Counter(position["health"] for position in response.json() if position["fiscal_year"] == utc_today().year)
    assert response.status_code == 200
    assert health["over"] == 1
    assert health["warning"] >= 2
    assert health["ok"] >= 1


async def test_the_company_can_be_used_through_its_screens_endpoints(
    seeded: tuple[DemoSeedSummary, async_sessionmaker[AsyncSession]], client: AsyncClient
) -> None:
    _, factory = seeded
    async with factory() as db:
        admin_id = await db.scalar(select(User.id).where(User.email == ACCOUNTS_BY_KEY["admin"].email))
    headers = {"Authorization": f"Bearer {create_access_token(str(admin_id), 'admin')}"}

    responses = [
        await client.get(f"{API}{path}", headers=headers)
        for path in ("/dashboard/summary", "/purchase-orders", "/supplier-invoices", "/payment-runs", "/suppliers")
    ]

    assert [response.status_code for response in responses] == [200] * len(responses)


async def test_resetting_twice_gives_the_same_company(
    demo_settings: Settings, demo_db: async_sessionmaker[AsyncSession]
) -> None:
    first = await reset_demo(demo_settings, demo_db)
    async with demo_db() as db:
        first_numbers = sorted((await db.scalars(select(PurchaseOrder.po_number))).all())
        first_invoices = sorted((await db.scalars(select(SupplierInvoice.invoice_number))).all())

    second = await reset_demo(demo_settings, demo_db)
    async with demo_db() as db:
        second_numbers = sorted((await db.scalars(select(PurchaseOrder.po_number))).all())
        second_invoices = sorted((await db.scalars(select(SupplierInvoice.invoice_number))).all())
        demo_users = await _scalar_count(db, select(func.count()).select_from(User))

    assert first == second
    assert (first_numbers, first_invoices) == (second_numbers, second_invoices)
    assert demo_users == len(DEMO_ACCOUNTS)


async def test_the_reset_removes_what_visitors_added(
    demo_settings: Settings, demo_db: async_sessionmaker[AsyncSession]
) -> None:
    await reset_demo(demo_settings, demo_db)
    async with demo_db() as db:
        db.add(Supplier(name="Added by a visitor", email="visitor@example.com"))
        await db.commit()

    await reset_demo(demo_settings, demo_db)

    async with demo_db() as db:
        assert await db.scalar(select(Supplier.id).where(Supplier.name == "Added by a visitor")) is None
        assert await _scalar_count(db, select(func.count()).select_from(Supplier)) == 8


async def test_the_reset_refuses_to_run_outside_the_demo(
    demo_db: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    db_session.add(Supplier(name="Real supplier", email="real@example.com"))
    await db_session.commit()

    with pytest.raises(DemoResetRefusedError, match="DEMO_MODE is not true"):
        await reset_demo(get_settings(), demo_db)

    assert await _scalar_count(db_session, select(func.count()).select_from(Supplier)) == 1


def test_the_seed_plan_is_deterministic() -> None:
    today = date(2026, 11, 3)

    assert build_order_plans(today) == build_order_plans(today)
    assert build_order_plans(today) != build_order_plans(today, seed=7)
