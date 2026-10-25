from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.catalog import CatalogItem
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User
from app.schemas.catalog import CatalogItemCreate, CatalogItemRead, CatalogItemUpdate
from app.services.audit_service import current_values, field_changes, record_audit_event
from app.services.po_pricing import resolve_currency

_LOAD = (selectinload(CatalogItem.product), selectinload(CatalogItem.supplier))


def is_current(item: CatalogItem, today: date) -> bool:
    """Usable today: switched on and inside its contract dates. Worked out per request, never stored."""
    if not item.is_active:
        return False
    if item.valid_from is not None and today < item.valid_from:
        return False
    return item.valid_until is None or today <= item.valid_until


def to_read(item: CatalogItem, today: date) -> CatalogItemRead:
    return CatalogItemRead(
        id=item.id,
        product_id=item.product_id,
        product_sku=item.product.sku,
        product_name=item.product.name,
        supplier_id=item.supplier_id,
        supplier_name=item.supplier.name,
        contract_price=item.contract_price,
        currency_code=item.currency_code,
        lead_time_days=item.lead_time_days,
        valid_from=item.valid_from,
        valid_until=item.valid_until,
        is_active=item.is_active,
        is_current=is_current(item, today),
        created_at=item.created_at,
    )


async def list_items(
    db: AsyncSession,
    *,
    supplier_id: int | None = None,
    product_id: int | None = None,
    search: str | None = None,
    active_only: bool = False,
) -> list[CatalogItem]:
    stmt = (
        select(CatalogItem)
        .options(*_LOAD)
        .join(Product, Product.id == CatalogItem.product_id)
        .join(Supplier, Supplier.id == CatalogItem.supplier_id)
        .order_by(Product.name, Supplier.name, CatalogItem.id)
    )
    if supplier_id is not None:
        stmt = stmt.where(CatalogItem.supplier_id == supplier_id)
    if product_id is not None:
        stmt = stmt.where(CatalogItem.product_id == product_id)
    if active_only:
        stmt = stmt.where(CatalogItem.is_active.is_(True))
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(or_(Product.name.ilike(pattern), Product.sku.ilike(pattern), Supplier.name.ilike(pattern)))
    return list((await db.execute(stmt)).scalars().all())


async def _get(db: AsyncSession, item_id: int) -> CatalogItem:
    item = await db.scalar(
        select(CatalogItem).options(*_LOAD).where(CatalogItem.id == item_id).execution_options(populate_existing=True)
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog item not found")
    return item


async def get_usable_item(db: AsyncSession, item_id: int, today: date) -> CatalogItem:
    """A catalog item a request line may use today; a client mistake (400) rather than a missing page otherwise."""
    item = await db.scalar(select(CatalogItem).where(CatalogItem.id == item_id))
    if item is None or not is_current(item, today):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Catalog item {item_id} is unknown or not valid today"
        )
    return item


async def create_item(db: AsyncSession, payload: CatalogItemCreate, user: User) -> CatalogItem:
    product = await db.get(Product, payload.product_id)
    supplier = await db.get(Supplier, payload.supplier_id)
    if product is None or supplier is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Product or supplier not found")
    currency = await resolve_currency(db, payload.currency_code, supplier)
    item = CatalogItem(
        product_id=product.id,
        supplier_id=supplier.id,
        contract_price=payload.contract_price,
        currency_code=currency.code,
        lead_time_days=payload.lead_time_days,
        valid_from=payload.valid_from,
        valid_until=payload.valid_until,
    )
    db.add(item)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This supplier already has a catalog entry for this product in this currency",
        ) from exc
    await record_audit_event(
        db,
        user_id=user.id,
        action="catalog_item_created",
        entity_type="catalog_item",
        entity_id=item.id,
        extra_data={"product_id": product.id, "supplier_id": supplier.id, "price": str(payload.contract_price)},
    )
    await db.commit()
    return await _get(db, item.id)


async def update_item(db: AsyncSession, item_id: int, payload: CatalogItemUpdate, user: User) -> CatalogItem:
    item = await _get(db, item_id)
    update_data = payload.model_dump(exclude_unset=True)
    for field in ("contract_price", "lead_time_days", "is_active"):
        if field in update_data and update_data[field] is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"'{field}' cannot be empty")
    valid_from = update_data.get("valid_from", item.valid_from)
    valid_until = update_data.get("valid_until", item.valid_until)
    if valid_from is not None and valid_until is not None and valid_until < valid_from:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="The contract cannot end before it starts"
        )
    changes = field_changes(current_values(item, update_data), update_data)
    for field, value in update_data.items():
        setattr(item, field, value)
    if changes:
        await record_audit_event(
            db,
            user_id=user.id,
            action="catalog_item_updated",
            entity_type="catalog_item",
            entity_id=item.id,
            extra_data={"changes": changes},
        )
    await db.commit()
    return await _get(db, item_id)
