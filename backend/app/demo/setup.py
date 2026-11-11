"""Seed step 1: the company's foundations (settings, people, rates, taxes, suppliers, products, cost centres).

Everything goes through the API as the person who would do it. The only direct database work is bootstrapping the
first administrator (nobody can create the first account through an API that needs one) and the demo password of
the two supplier-portal accounts (their owners would normally choose it from the emailed invitation link).
"""

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.security import hash_password
from app.demo.accounts import ACCOUNTS_BY_KEY, DEMO_ACCOUNTS, demo_password
from app.demo.api import DemoApi
from app.demo.catalog import (
    BASE_CURRENCY,
    CATEGORIES,
    COMPANY_NAME,
    COST_CENTRES,
    EXCHANGE_RATES,
    PRODUCTS,
    SUPPLIERS,
    TAX_RATES,
    TIMEZONE,
)
from app.demo.plan import MONTHS, months_back
from app.models.user import User
from app.seeds.seed import seed_permissions_and_roles

PLACEHOLDER_BUDGET = "1000000.00"
RATE_DRIFT_BASIS_POINTS = 150
# The company's own account for payment files (documented public example identifiers, not a real account).
PAYER = {
    "payer_iban": "NL91ABNA0417164300",
    "payer_bic": "ABNANL2A",
    "payer_routing_number": "011000015",
    "payer_account_number": "1234567890",
    "ach_company_id": "1234567890",
}


@dataclass
class Foundation:
    """The ids the later steps need, by the names they use."""

    role_ids: dict[str, int] = field(default_factory=dict)
    category_ids: dict[str, int] = field(default_factory=dict)
    supplier_ids: dict[str, int] = field(default_factory=dict)
    product_ids: dict[str, int] = field(default_factory=dict)
    cost_centre_ids: dict[str, int] = field(default_factory=dict)
    tax_ids: dict[str, int] = field(default_factory=dict)


async def create_admin(
    session_factory: async_sessionmaker[AsyncSession], api: DemoApi, settings: Settings
) -> dict[str, int]:
    """Roles and permissions (idempotent, as in the normal seed) and the demo administrator; returns role ids."""
    admin = ACCOUNTS_BY_KEY["admin"]
    async with session_factory() as db:
        roles = await seed_permissions_and_roles(db)
        user = User(
            email=admin.email,
            full_name=admin.full_name,
            hashed_password=hash_password(demo_password(settings)),
            role_id=roles[admin.role_name].id,
        )
        db.add(user)
        await db.flush()
        await db.commit()
        api.register("admin", user.id, admin.role_name)
        return {name: role.id for name, role in roles.items()}


async def create_staff(api: DemoApi, settings: Settings, role_ids: dict[str, int]) -> None:
    """The internal demo users, created by the administrator."""
    for account in DEMO_ACCOUNTS:
        if account.key == "admin" or account.is_portal:
            continue
        created = await api.post(
            "admin",
            "/users",
            {
                "email": account.email,
                "full_name": account.full_name,
                "password": demo_password(settings),
                "role_id": role_ids[account.role_name],
            },
        )
        api.register(account.key, created["id"], account.role_name)


async def configure_company(api: DemoApi) -> None:
    await api.patch(
        "admin",
        "/company-settings",
        {
            "company_name": COMPANY_NAME,
            "legal_name": "Northbridge Trading Company, Inc.",
            "address_line1": "500 N Michigan Avenue",
            "city": "Chicago",
            "region": "IL",
            "postal_code": "60611",
            "country_code": "US",
            "tax_id": "US-36-0098765",
            "contact_email": "purchasing@northbridge-trading.example.com",
            "contact_phone": "+1 312 555 0100",
            "brand_color": "#0F766E",
            "base_currency_code": BASE_CURRENCY,
            "timezone": TIMEZONE,
            "date_format": "MM/DD/YYYY",
            "invoice_tolerance_percent": "2.00",
            "default_payment_terms_days": 30,
            "budget_warn_percent": "80.00",
            **PAYER,
        },
    )


async def load_exchange_rates(api: DemoApi, today: date, rng: random.Random) -> None:
    """A rate on the first of each of the last twelve months and one for today, drifting gently."""
    days = [months_back(today, months, 1) for months in range(MONTHS, 0, -1)] + [today]
    for currency, base_rate in EXCHANGE_RATES.items():
        for day in days:
            drift = Decimal(rng.randint(-RATE_DRIFT_BASIS_POINTS, RATE_DRIFT_BASIS_POINTS)) / Decimal(10_000)
            rate = (base_rate * (Decimal(1) + drift)).quantize(Decimal("0.0001"))
            await api.post(
                "finance", "/exchange-rates", {"currency_code": currency, "rate": str(rate), "effective_date": str(day)}
            )


async def create_taxes(api: DemoApi, foundation: Foundation) -> None:
    for key, (name, percentage, region) in TAX_RATES.items():
        created = await api.post(
            "finance", "/tax-rates", {"name": name, "percentage": percentage, "tax_type": "vat", "region": region}
        )
        foundation.tax_ids[key] = created["id"]


async def create_suppliers(api: DemoApi, foundation: Foundation) -> None:
    for supplier in SUPPLIERS:
        created = await api.post(
            "procurement_manager",
            "/suppliers",
            {
                "name": supplier.name,
                "contact_name": supplier.contact_name,
                "email": supplier.email,
                "phone": supplier.phone,
                "address": supplier.address,
                "country_code": supplier.country_code,
                "tax_id": supplier.tax_id,
                "currency_code": supplier.currency_code,
                "payment_terms_days": supplier.payment_terms_days,
            },
        )
        foundation.supplier_ids[supplier.name] = created["id"]
        if supplier.iban is not None:
            base = f"/suppliers/{created['id']}/bank-details/changes"
            change = await api.post(
                "finance",
                base,
                {
                    "bank_account_name": supplier.name,
                    "bank_country": supplier.country_code,
                    "iban": supplier.iban,
                    "bic": supplier.bic,
                },
            )
            # Bank details only take effect when a second person approves them.
            await api.post("finance_approver", f"{base}/{change['id']}/approve", {})


async def create_products(api: DemoApi, foundation: Foundation) -> None:
    for name in CATEGORIES:
        foundation.category_ids[name] = (await api.post("procurement_manager", "/categories", {"name": name}))["id"]
    for product in PRODUCTS:
        created = await api.post(
            "procurement_manager",
            "/products",
            {
                "sku": product.sku,
                "name": product.name,
                "category_id": foundation.category_ids[product.category],
                "unit": product.unit,
                "cost": str(product.price),
                "minimum_stock": product.minimum_stock,
                "supplier_id": foundation.supplier_ids[product.supplier],
            },
        )
        foundation.product_ids[product.sku] = created["id"]
        await api.post(
            "warehouse_manager",
            "/inventory/opening-balance",
            {"product_id": created["id"], "quantity": product.opening_stock, "reason": "Opening stock count"},
        )


async def create_cost_centres(api: DemoApi, foundation: Foundation, fiscal_years: tuple[int, ...]) -> None:
    for centre in COST_CENTRES:
        created = await api.post(
            "finance",
            "/cost-centres",
            {"code": centre.code, "name": centre.name, "manager_id": api.user_id(centre.manager_key)},
        )
        foundation.cost_centre_ids[centre.code] = created["id"]
        for fiscal_year in fiscal_years:
            # Real amounts are set at the end, once the year's spending is known (see app.demo.budgets).
            await api.put(
                "finance",
                "/budgets",
                {
                    "cost_centre_id": created["id"],
                    "fiscal_year": fiscal_year,
                    "amount": PLACEHOLDER_BUDGET,
                    "reason": "Annual budget",
                },
            )


async def create_approval_setup(api: DemoApi, today: date, role_ids: dict[str, int]) -> None:
    """Two purchase-order approval rules and a delegation: Priya Raman's approvals are covered by Marcus Webb."""
    steps_one = [{"approver_role_id": role_ids["procurement_manager"]}]
    steps_two = [*steps_one, {"approver_role_id": role_ids["finance"]}]
    for name, low, high, steps in (
        ("Standard orders", "0", "20000", steps_one),
        ("Large orders: manager, then finance", "20000", None, steps_two),
    ):
        await api.post(
            "finance",
            "/approval-rules",
            {"name": name, "document_type": "purchase_order", "min_amount": low, "max_amount": high, "steps": steps},
        )
    await api.post(
        "procurement_manager",
        "/approval-delegations",
        {
            "delegate_id": api.user_id("department_manager"),
            "starts_on": str(today - timedelta(days=21)),
            "ends_on": str(today + timedelta(days=21)),
        },
    )


async def invite_portal_suppliers(
    api: DemoApi, session_factory: async_sessionmaker[AsyncSession], settings: Settings, foundation: Foundation
) -> None:
    """Invite the two portal contacts, then give their accounts the demo password."""
    for account in (a for a in DEMO_ACCOUNTS if a.is_portal):
        supplier_id = foundation.supplier_ids[account.supplier_name or ""]
        invited = await api.post(
            "procurement_manager",
            f"/suppliers/{supplier_id}/portal-invite",
            {"email": account.email, "full_name": account.full_name},
        )
        api.register(account.key, invited["id"], account.role_name)
    async with session_factory() as db:
        emails = [a.email for a in DEMO_ACCOUNTS if a.is_portal]
        await db.execute(
            update(User).where(User.email.in_(emails)).values(hashed_password=hash_password(demo_password(settings)))
        )
        await db.commit()
