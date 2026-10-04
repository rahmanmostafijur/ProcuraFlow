from collections.abc import Callable

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import verify_password
from app.models.role import Role
from app.models.user import User
from app.seeds.seed import UnsafeAdminPasswordError, ensure_admin_password_is_safe, seed_admin_user

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
