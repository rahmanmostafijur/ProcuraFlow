import asyncio
from collections.abc import Callable

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import verify_password
from app.models.enums import InventoryTransactionType
from app.models.inventory import InventoryTransaction
from app.models.product import Product
from app.models.role import Role
from app.models.supplier import Supplier
from app.models.user import User
from app.seeds.seed import (
    UnsafeAdminPasswordError,
    ensure_admin_password_is_safe,
    run_seed,
    seed_admin_user,
    seed_demo_data,
)

STRONG_SECRET = "k3Vq9xLr0TzP7mWb2NcY8sHd5FgJ1aUe6RoXiQ4vEyZt"
STRONG_PASSWORD = "Vq9-xLr0-TzP7-mWb2"
ADMIN_EMAIL = "seed-admin@example.com"


def make_settings(environment: str, password: str) -> Settings:
    return Settings(
        _env_file=None,
        environment=environment,
        jwt_secret_key=STRONG_SECRET,
        default_admin_email=ADMIN_EMAIL,
        default_admin_password=password,
    )


async def find_admin(db_session: AsyncSession) -> User | None:
    return (await db_session.execute(select(User).where(User.email == ADMIN_EMAIL))).scalar_one_or_none()


@pytest.mark.parametrize("environment", ["production", "staging"])
@pytest.mark.parametrize("password", ["change-this-admin-password", "ChangeMe123!"])
def test_guard_rejects_known_default_passwords(environment: str, password: str):
    with pytest.raises(UnsafeAdminPasswordError, match="DEFAULT_ADMIN_PASSWORD is a known default"):
        ensure_admin_password_is_safe(make_settings(environment, password))


def test_guard_rejects_short_password_in_production():
    with pytest.raises(UnsafeAdminPasswordError, match="at least 12 characters"):
        ensure_admin_password_is_safe(make_settings("production", "Sh0rt-pass!"))


def test_guard_accepts_strong_password_in_production():
    ensure_admin_password_is_safe(make_settings("production", STRONG_PASSWORD))


@pytest.mark.parametrize("environment", ["development", "test"])
def test_guard_allows_default_password_locally(environment: str):
    ensure_admin_password_is_safe(make_settings(environment, "ChangeMe123!"))


async def test_seed_refuses_to_create_admin_with_default_password_in_production(
    db_session: AsyncSession, roles: dict[str, Role]
):
    with pytest.raises(UnsafeAdminPasswordError):
        await seed_admin_user(db_session, roles, make_settings("production", "ChangeMe123!"))

    assert await find_admin(db_session) is None


async def test_seed_creates_admin_with_strong_password_in_production(
    db_session: AsyncSession, roles: dict[str, Role]
):
    await seed_admin_user(db_session, roles, make_settings("production", STRONG_PASSWORD))
    await db_session.flush()

    admin = await find_admin(db_session)
    assert admin is not None
    assert verify_password(STRONG_PASSWORD, admin.hashed_password)


async def test_seed_never_overwrites_existing_admin_password(
    db_session: AsyncSession, make_user: Callable, roles: dict[str, Role]
):
    await make_user(ADMIN_EMAIL, "admin", password="Original-Pass-123")

    await seed_admin_user(db_session, roles, make_settings("production", STRONG_PASSWORD))
    await db_session.flush()

    admin = await find_admin(db_session)
    await db_session.refresh(admin)
    assert verify_password("Original-Pass-123", admin.hashed_password)
    assert not verify_password(STRONG_PASSWORD, admin.hashed_password)


async def _row_counts(db_session: AsyncSession) -> list[int]:
    return [
        await db_session.scalar(select(func.count()).select_from(model)) for model in (Product, InventoryTransaction)
    ]


async def test_seed_records_demo_opening_stock_through_the_ledger(
    db_session: AsyncSession, roles: dict[str, Role], assert_stock_matches_ledger
):
    admin = await seed_admin_user(db_session, roles, make_settings("test", "ChangeMe123!"))
    await seed_demo_data(db_session, admin)
    await db_session.commit()

    products = (await db_session.execute(select(Product))).scalars().all()
    ledger = (await db_session.execute(select(InventoryTransaction))).scalars().all()
    assert products
    assert all(product.current_stock > 0 for product in products)
    assert sorted(row.product_id for row in ledger) == sorted(product.id for product in products)
    assert {row.type for row in ledger} == {InventoryTransactionType.OPENING_BALANCE}
    assert {row.created_by for row in ledger} == {admin.id}
    for product in products:
        await assert_stock_matches_ledger(product.id)


async def test_seed_demo_data_is_idempotent(db_session: AsyncSession, roles: dict[str, Role]):
    admin = await seed_admin_user(db_session, roles, make_settings("test", "ChangeMe123!"))
    await seed_demo_data(db_session, admin)
    await db_session.commit()
    counts = await _row_counts(db_session)

    again = await seed_admin_user(db_session, roles, make_settings("test", "ChangeMe123!"))
    await seed_demo_data(db_session, again)
    await db_session.commit()

    assert again.id == admin.id
    assert await _row_counts(db_session) == counts


@pytest.mark.parametrize(
    "environment, expected",
    [("development", True), ("test", True), ("staging", False), ("production", False)],
)
def test_demo_data_is_seeded_by_default_only_in_local_environments(
    environment: str, expected: bool, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("SEED_DEMO_DATA", raising=False)

    assert make_settings(environment, STRONG_PASSWORD).should_seed_demo_data is expected


@pytest.mark.parametrize("flag", [True, False])
def test_an_explicit_seed_demo_data_setting_overrides_the_environment_default(flag: bool):
    settings = Settings(_env_file=None, environment="production", jwt_secret_key=STRONG_SECRET, seed_demo_data=flag)

    assert settings.should_seed_demo_data is flag


async def test_production_seed_creates_roles_and_admin_but_no_demo_catalogue_by_default(
    db_session: AsyncSession, session_factory, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("SEED_DEMO_DATA", raising=False)

    await run_seed(make_settings("production", STRONG_PASSWORD), session_factory)

    assert await find_admin(db_session) is not None
    assert await db_session.scalar(select(func.count()).select_from(Role)) > 0
    assert await db_session.scalar(select(func.count()).select_from(Supplier)) == 0
    assert await db_session.scalar(select(func.count()).select_from(Product)) == 0


async def test_seed_adds_the_demo_catalogue_when_explicitly_enabled_and_stays_idempotent(
    db_session: AsyncSession, session_factory
):
    settings = Settings(
        _env_file=None,
        environment="production",
        jwt_secret_key=STRONG_SECRET,
        default_admin_email=ADMIN_EMAIL,
        default_admin_password=STRONG_PASSWORD,
        seed_demo_data=True,
    )

    await run_seed(settings, session_factory)
    await run_seed(settings, session_factory)

    assert await db_session.scalar(select(func.count()).select_from(Supplier)) == 3
    assert await db_session.scalar(select(func.count()).select_from(Product)) == 6
    assert await db_session.scalar(select(func.count()).select_from(User).where(User.email == ADMIN_EMAIL)) == 1


async def test_several_instances_seeding_at_once_do_not_collide(db_session: AsyncSession, session_factory):
    settings = Settings(
        _env_file=None,
        environment="production",
        jwt_secret_key=STRONG_SECRET,
        default_admin_email=ADMIN_EMAIL,
        default_admin_password=STRONG_PASSWORD,
        seed_demo_data=True,
    )

    await asyncio.gather(*[run_seed(settings, session_factory) for _ in range(3)])

    assert await db_session.scalar(select(func.count()).select_from(User).where(User.email == ADMIN_EMAIL)) == 1
    assert await db_session.scalar(select(func.count()).select_from(Role)) == 5
    assert await db_session.scalar(select(func.count()).select_from(Supplier)) == 3
