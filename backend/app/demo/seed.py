"""The demo seed: a fictional US/EU company's last twelve months, built through the application's own API.

Order of work (each step is a module in this package):
    setup      company settings, people, exchange rates, taxes, suppliers, products with opening stock, cost centres,
               approval rules and a delegation, supplier-portal invitations
    year       three orders a month for twelve months, each taken as far through procure-to-pay as the plan says
    scenarios  the situations a demo must show: delegated approval, amendments, partial receipt with a return,
               duplicate invoice, price exception, orders needing two approvals, a released SEPA payment run
    extras     supplier documents (one expired, one expiring), open purchase requests, final stock levels
    timeline   documents get the dates the plan gave them
    budgets    cost-centre budgets set so some are near their limit and one is over

The seed runs on an empty database (``demo_reset`` empties it first). It is deterministic: a seeded random generator
and today's date decide everything, so the same day always produces the same company.
"""

import logging
import random
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.clock import today_in
from app.core.config import Settings
from app.core.demo_guard import seeding_allowed
from app.core.fiscal import fiscal_year_of
from app.demo import budgets, extras, scenarios, setup, timeline
from app.demo.api import open_demo_api
from app.demo.catalog import TIMEZONE
from app.demo.plan import SEED, build_order_plans
from app.demo.year import SeedContext, run_regular_orders
from app.models.payment import Payment
from app.models.purchase_order import PurchaseOrder
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice
from app.models.user import User

logger = logging.getLogger(__name__)
FISCAL_YEAR_START_MONTH = 1


@dataclass(frozen=True)
class DemoSeedSummary:
    users: int
    suppliers: int
    purchase_orders: int
    invoices: int
    payments: int
    sepa_run_number: str | None


async def seed_demo(settings: Settings, session_factory: async_sessionmaker[AsyncSession]) -> DemoSeedSummary:
    """Build the demo company. The database must hold no demo data yet."""
    today = today_in(TIMEZONE)
    rng = random.Random(SEED)  # noqa: S311 - reproducible demo data, not a secret
    with seeding_allowed():
        async with open_demo_api() as api:
            role_ids = await setup.create_admin(session_factory, api, settings)
            await setup.create_staff(api, settings, role_ids)
            await setup.configure_company(api)
            await setup.load_exchange_rates(api, today, rng)
            foundation = setup.Foundation(role_ids=role_ids)
            await setup.create_taxes(api, foundation)
            await setup.create_suppliers(api, foundation)
            await setup.create_products(api, foundation)
            fiscal_year = fiscal_year_of(today, FISCAL_YEAR_START_MONTH)
            await setup.create_cost_centres(api, foundation, (fiscal_year - 1, fiscal_year))
            await setup.create_approval_setup(api, today, role_ids)
            await setup.invite_portal_suppliers(api, session_factory, settings, foundation)

            ctx = SeedContext(api=api, foundation=foundation, today=today)
            await run_regular_orders(ctx, build_order_plans(today))
            await scenarios.seed_scenarios(ctx)
            await extras.upload_documents(ctx)
            await extras.open_requests(ctx)
            await extras.settle_stock(api, foundation)
            await timeline.apply_timeline(session_factory, ctx.records)
            await budgets.tune_budgets(api, fiscal_year)
    logger.info("Demo data created for %s", today.isoformat())
    return await summarise(session_factory, ctx.sepa_run_number)


async def summarise(session_factory: async_sessionmaker[AsyncSession], sepa_run_number: str | None) -> DemoSeedSummary:
    async with session_factory() as db:
        users, suppliers, orders, invoices, payments = [
            await db.scalar(select(func.count()).select_from(model)) or 0
            for model in (User, Supplier, PurchaseOrder, SupplierInvoice, Payment)
        ]
    return DemoSeedSummary(users, suppliers, orders, invoices, payments, sepa_run_number)
