import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.permissions import PERMISSIONS, ROLE_DESCRIPTIONS, ROLE_PERMISSIONS
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.category import Category
from app.models.permission import Permission
from app.models.product import Product
from app.models.role import Role
from app.models.supplier import Supplier
from app.models.user import User

settings = get_settings()


async def seed_permissions_and_roles(db: AsyncSession) -> dict[str, Role]:
    existing_permissions = {p.code: p for p in (await db.execute(select(Permission))).scalars().all()}
    for code, description in PERMISSIONS.items():
        if code not in existing_permissions:
            permission = Permission(code=code, description=description)
            db.add(permission)
            existing_permissions[code] = permission
    await db.flush()

    existing_roles = {
        r.name: r
        for r in (await db.execute(select(Role).options(selectinload(Role.permissions)))).scalars().all()
    }
    for role_name, permission_codes in ROLE_PERMISSIONS.items():
        role = existing_roles.get(role_name)
        if role is None:
            role = Role(name=role_name, description=ROLE_DESCRIPTIONS.get(role_name))
            db.add(role)
            existing_roles[role_name] = role
        role.permissions = [existing_permissions[code] for code in permission_codes]
    await db.flush()
    return existing_roles


async def seed_admin_user(db: AsyncSession, roles: dict[str, Role]) -> None:
    existing = (
        await db.execute(select(User).where(User.email == settings.default_admin_email))
    ).scalar_one_or_none()
    if existing is not None:
        return

    admin_role = roles["admin"]
    db.add(
        User(
            email=settings.default_admin_email,
            hashed_password=hash_password(settings.default_admin_password),
            full_name="System Administrator",
            role_id=admin_role.id,
            is_active=True,
        )
    )


async def seed_demo_data(db: AsyncSession) -> None:
    existing_supplier = (await db.execute(select(Supplier))).scalars().first()
    if existing_supplier is not None:
        return

    categories = {
        name: Category(name=name) for name in ["Office Supplies", "Electronics", "Raw Materials", "Packaging"]
    }
    db.add_all(categories.values())
    await db.flush()

    suppliers = [
        Supplier(
            name="Acme Industrial Supply",
            contact_name="Jane Carter",
            email="jane@acmeindustrial.com",
            phone="555-0101",
            address="100 Industrial Way",
        ),
        Supplier(
            name="Northwind Electronics",
            contact_name="Raj Patel",
            email="raj@northwindelec.com",
            phone="555-0102",
            address="200 Circuit Ave",
        ),
        Supplier(
            name="Blue Ridge Packaging Co.",
            contact_name="Maria Gomez",
            email="maria@blueridgepack.com",
            phone="555-0103",
            address="300 Carton Blvd",
        ),
    ]
    db.add_all(suppliers)
    await db.flush()

    products = [
        Product(
            sku="OFF-1001",
            name="A4 Copy Paper (Ream)",
            category_id=categories["Office Supplies"].id,
            unit="ream",
            cost=4.50,
            current_stock=500,
            minimum_stock=100,
            supplier_id=suppliers[0].id,
        ),
        Product(
            sku="OFF-1002",
            name="Ballpoint Pens (Box of 50)",
            category_id=categories["Office Supplies"].id,
            unit="box",
            cost=8.25,
            current_stock=120,
            minimum_stock=30,
            supplier_id=suppliers[0].id,
        ),
        Product(
            sku="ELC-2001",
            name="USB-C Cable 1m",
            category_id=categories["Electronics"].id,
            unit="unit",
            cost=2.10,
            current_stock=40,
            minimum_stock=50,
            supplier_id=suppliers[1].id,
        ),
        Product(
            sku="ELC-2002",
            name="Wireless Mouse",
            category_id=categories["Electronics"].id,
            unit="unit",
            cost=11.75,
            current_stock=75,
            minimum_stock=20,
            supplier_id=suppliers[1].id,
        ),
        Product(
            sku="PKG-3001",
            name="Corrugated Box (Medium)",
            category_id=categories["Packaging"].id,
            unit="unit",
            cost=0.85,
            current_stock=800,
            minimum_stock=200,
            supplier_id=suppliers[2].id,
        ),
        Product(
            sku="RAW-4001",
            name="Aluminum Sheet 1mm",
            category_id=categories["Raw Materials"].id,
            unit="sheet",
            cost=15.00,
            current_stock=25,
            minimum_stock=30,
            supplier_id=suppliers[0].id,
        ),
    ]
    db.add_all(products)


async def run_seed() -> None:
    async with AsyncSessionLocal() as db:
        roles = await seed_permissions_and_roles(db)
        await seed_admin_user(db, roles)
        await seed_demo_data(db)
        await db.commit()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(run_seed())
