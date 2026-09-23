from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser, DbSession, require_permission
from app.core.pagination import paginate
from app.models.product import Product
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.product import ProductCreate, ProductRead, ProductUpdate
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/products", tags=["products"])

RequireProductWrite = Annotated[User, Depends(require_permission("product:write"))]

_LOAD_OPTIONS = (selectinload(Product.category), selectinload(Product.supplier))


@router.get("", response_model=PaginatedResponse[ProductRead])
async def list_products(
    db: DbSession,
    _: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    category_id: int | None = None,
    supplier_id: int | None = None,
    is_active: bool | None = None,
    low_stock_only: bool = False,
    sort_by: str = Query("name", pattern="^(name|sku|current_stock|cost)$"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
) -> PaginatedResponse[ProductRead]:
    stmt = select(Product).options(*_LOAD_OPTIONS)
    if search:
        stmt = stmt.where(Product.name.ilike(f"%{search}%") | Product.sku.ilike(f"%{search}%"))
    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    if supplier_id is not None:
        stmt = stmt.where(Product.supplier_id == supplier_id)
    if is_active is not None:
        stmt = stmt.where(Product.is_active == is_active)
    if low_stock_only:
        stmt = stmt.where(Product.current_stock <= Product.minimum_stock)

    sort_column = getattr(Product, sort_by)
    stmt = stmt.order_by(sort_column.desc() if sort_dir == "desc" else sort_column.asc())

    items, total, total_pages = await paginate(db, stmt, page, page_size)
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(product_id: int, db: DbSession, _: CurrentUser) -> Product:
    result = await db.execute(select(Product).options(*_LOAD_OPTIONS).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(payload: ProductCreate, db: DbSession, current_user: RequireProductWrite) -> Product:
    existing = await db.execute(select(Product).where(Product.sku == payload.sku))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A product with this SKU already exists")

    product = Product(**payload.model_dump())
    db.add(product)
    await db.flush()
    await record_audit_event(
        db, user_id=current_user.id, action="product_created", entity_type="product", entity_id=product.id
    )
    await db.commit()

    result = await db.execute(select(Product).options(*_LOAD_OPTIONS).where(Product.id == product.id))
    return result.scalar_one()


@router.patch("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: int, payload: ProductUpdate, db: DbSession, current_user: RequireProductWrite
) -> Product:
    result = await db.execute(select(Product).options(*_LOAD_OPTIONS).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)

    await record_audit_event(
        db, user_id=current_user.id, action="product_updated", entity_type="product", entity_id=product.id
    )
    await db.commit()

    result = await db.execute(select(Product).options(*_LOAD_OPTIONS).where(Product.id == product_id))
    return result.scalar_one()
