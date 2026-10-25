from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.clock import today_in
from app.core.deps import CurrentUser, DbSession, require_permission
from app.models.user import User
from app.schemas.catalog import CatalogItemCreate, CatalogItemRead, CatalogItemUpdate
from app.services import catalog_service
from app.services.company_settings_service import get_company_settings

router = APIRouter(prefix="/catalog-items", tags=["catalog"])

RequireCatalogManage = Annotated[User, Depends(require_permission("catalog:manage"))]


@router.get("", response_model=list[CatalogItemRead])
async def list_items(
    db: DbSession,
    _: CurrentUser,
    supplier_id: int | None = None,
    product_id: int | None = None,
    search: str | None = None,
    active_only: bool = False,
) -> list[CatalogItemRead]:
    today = today_in((await get_company_settings(db)).timezone)
    items = await catalog_service.list_items(
        db, supplier_id=supplier_id, product_id=product_id, search=search, active_only=active_only
    )
    return [catalog_service.to_read(item, today) for item in items]


@router.post("", response_model=CatalogItemRead, status_code=status.HTTP_201_CREATED)
async def create_item(payload: CatalogItemCreate, db: DbSession, user: RequireCatalogManage) -> CatalogItemRead:
    item = await catalog_service.create_item(db, payload, user)
    return catalog_service.to_read(item, today_in((await get_company_settings(db)).timezone))


@router.patch("/{item_id}", response_model=CatalogItemRead)
async def update_item(
    item_id: int, payload: CatalogItemUpdate, db: DbSession, user: RequireCatalogManage
) -> CatalogItemRead:
    item = await catalog_service.update_item(db, item_id, payload, user)
    return catalog_service.to_read(item, today_in((await get_company_settings(db)).timezone))
