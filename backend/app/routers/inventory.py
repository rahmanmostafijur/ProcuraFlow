from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession, require_permission
from app.core.pagination import paginate
from app.models.enums import InventoryTransactionType
from app.models.inventory import InventoryTransaction
from app.models.product import Product
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.inventory import InventoryAdjustmentCreate, InventoryTransactionRead
from app.services.audit_service import record_audit_event
from app.services.inventory_service import apply_inventory_transaction

router = APIRouter(prefix="/inventory", tags=["inventory"])

RequireInventoryWrite = Annotated[User, Depends(require_permission("inventory:write"))]


@router.get("/transactions", response_model=PaginatedResponse[InventoryTransactionRead])
async def list_inventory_transactions(
    db: DbSession,
    _: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    product_id: int | None = None,
) -> PaginatedResponse[InventoryTransactionRead]:
    stmt = select(InventoryTransaction).order_by(InventoryTransaction.created_at.desc())
    if product_id is not None:
        stmt = stmt.where(InventoryTransaction.product_id == product_id)

    items, total, total_pages = await paginate(db, stmt, page, page_size)
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)


@router.post("/adjustments", response_model=InventoryTransactionRead, status_code=status.HTTP_201_CREATED)
async def create_adjustment(
    payload: InventoryAdjustmentCreate, db: DbSession, current_user: RequireInventoryWrite
) -> InventoryTransaction:
    product = await db.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    transaction = await apply_inventory_transaction(
        db,
        product=product,
        quantity_delta=payload.quantity_delta,
        transaction_type=InventoryTransactionType.ADJUSTMENT,
        created_by=current_user.id,
        reason=payload.reason,
    )
    await db.flush()
    await record_audit_event(
        db,
        user_id=current_user.id,
        action="inventory_adjusted",
        entity_type="product",
        entity_id=product.id,
        extra_data={"quantity_delta": payload.quantity_delta, "reason": payload.reason},
    )
    await db.commit()
    await db.refresh(transaction)
    return transaction
