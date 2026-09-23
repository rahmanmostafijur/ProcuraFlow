from collections.abc import AsyncGenerator, Callable

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.permissions import PERMISSIONS, ROLE_DESCRIPTIONS, ROLE_PERMISSIONS
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.permission import Permission
from app.models.product import Product
from app.models.role import Role
from app.models.supplier import Supplier
from app.models.user import User

settings = get_settings()

test_engine = create_async_engine(settings.test_database_url, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(bind=test_engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await test_engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def clean_tables():
    yield
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = _override_get_db


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def roles(db_session: AsyncSession) -> dict[str, Role]:
    permission_objs = {code: Permission(code=code, description=desc) for code, desc in PERMISSIONS.items()}
    db_session.add_all(permission_objs.values())
    await db_session.flush()

    role_objs: dict[str, Role] = {}
    for role_name, codes in ROLE_PERMISSIONS.items():
        role = Role(name=role_name, description=ROLE_DESCRIPTIONS.get(role_name))
        role.permissions = [permission_objs[code] for code in codes]
        db_session.add(role)
        role_objs[role_name] = role
    await db_session.commit()
    for role in role_objs.values():
        await db_session.refresh(role)
    return role_objs


@pytest_asyncio.fixture
async def make_user(db_session: AsyncSession, roles: dict[str, Role]) -> Callable:
    async def _make_user(email: str, role_name: str, password: str = "TestPass123!") -> User:
        user = User(
            email=email,
            full_name=f"{role_name.title()} User",
            hashed_password=hash_password(password),
            role_id=roles[role_name].id,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    return _make_user


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient, make_user: Callable) -> Callable:
    async def _auth_headers(role_name: str, email: str | None = None) -> dict[str, str]:
        email = email or f"{role_name}@example.com"
        await make_user(email, role_name)
        response = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "TestPass123!"}
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _auth_headers


@pytest_asyncio.fixture
async def supplier(db_session: AsyncSession) -> Supplier:
    supplier_obj = Supplier(name="Test Supplier", email="supplier@example.com")
    db_session.add(supplier_obj)
    await db_session.commit()
    await db_session.refresh(supplier_obj)
    return supplier_obj


@pytest_asyncio.fixture
async def product(db_session: AsyncSession, supplier: Supplier) -> Product:
    product_obj = Product(
        sku="TEST-001",
        name="Test Widget",
        cost=10,
        current_stock=50,
        minimum_stock=10,
        supplier_id=supplier.id,
    )
    db_session.add(product_obj)
    await db_session.commit()
    await db_session.refresh(product_obj)
    return product_obj
