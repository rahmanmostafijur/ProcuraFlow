from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession, require_permission
from app.core.pagination import paginate
from app.models.supplier import Supplier
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.supplier import SupplierCreate, SupplierRead, SupplierUpdate
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/suppliers", tags=["suppliers"])

RequireSupplierWrite = Annotated[User, Depends(require_permission("supplier:write"))]


@router.get("", response_model=PaginatedResponse[SupplierRead])
async def list_suppliers(
    db: DbSession,
    _: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    is_active: bool | None = None,
    sort_by: str = Query("name", pattern="^(name|created_at)$"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
) -> PaginatedResponse[SupplierRead]:
    stmt = select(Supplier)
    if search:
        stmt = stmt.where(Supplier.name.ilike(f"%{search}%"))
    if is_active is not None:
        stmt = stmt.where(Supplier.is_active == is_active)

    sort_column = getattr(Supplier, sort_by)
    stmt = stmt.order_by(sort_column.desc() if sort_dir == "desc" else sort_column.asc())

    items, total, total_pages = await paginate(db, stmt, page, page_size)
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)


@router.get("/{supplier_id}", response_model=SupplierRead)
async def get_supplier(supplier_id: int, db: DbSession, _: CurrentUser) -> Supplier:
    supplier = await db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    return supplier


@router.post("", response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    payload: SupplierCreate, db: DbSession, current_user: RequireSupplierWrite
) -> Supplier:
    supplier = Supplier(**payload.model_dump())
    db.add(supplier)
    await db.flush()
    await record_audit_event(
        db, user_id=current_user.id, action="supplier_created", entity_type="supplier", entity_id=supplier.id
    )
    await db.commit()
    await db.refresh(supplier)
    return supplier


@router.patch("/{supplier_id}", response_model=SupplierRead)
async def update_supplier(
    supplier_id: int, payload: SupplierUpdate, db: DbSession, current_user: RequireSupplierWrite
) -> Supplier:
    supplier = await db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(supplier, field, value)

    await record_audit_event(
        db, user_id=current_user.id, action="supplier_updated", entity_type="supplier", entity_id=supplier.id
    )
    await db.commit()
    await db.refresh(supplier)
    return supplier
