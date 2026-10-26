from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.deps import CurrentUser, DbSession, require_permission
from app.core.pagination import paginate_mapped
from app.models.enums import ReturnStatus
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.supplier_return import SupplierReturnCreate, SupplierReturnRead, SupplierReturnStatusChange
from app.services import supplier_return_service as service

router = APIRouter(prefix="/supplier-returns", tags=["supplier-returns"])

RequireInventoryWrite = Annotated[User, Depends(require_permission("inventory:write"))]


@router.get("", response_model=PaginatedResponse[SupplierReturnRead])
async def list_returns(
    db: DbSession,
    _: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Annotated[ReturnStatus | None, Query(alias="status")] = None,
    po_id: int | None = None,
    supplier_id: int | None = None,
) -> PaginatedResponse[SupplierReturnRead]:
    stmt = service.list_statement(status_filter, po_id, supplier_id)
    return await paginate_mapped(db, stmt, page, page_size, service.to_read)


@router.post("", response_model=SupplierReturnRead, status_code=status.HTTP_201_CREATED)
async def create_return(
    payload: SupplierReturnCreate, db: DbSession, user: RequireInventoryWrite
) -> SupplierReturnRead:
    """Return rejected units of an order to the supplier: at most the rejected units not yet on another return."""
    return service.to_read(await service.create_return(db, payload, user))


@router.get("/{return_id}", response_model=SupplierReturnRead)
async def get_return(return_id: int, db: DbSession, _: CurrentUser) -> SupplierReturnRead:
    return service.to_read(await service.get_return(db, return_id))


@router.post("/{return_id}/status", response_model=SupplierReturnRead)
async def change_return_status(
    return_id: int, payload: SupplierReturnStatusChange, db: DbSession, user: RequireInventoryWrite
) -> SupplierReturnRead:
    """Move a return forward (open, sent, resolved) or cancel it."""
    return service.to_read(await service.change_status(db, return_id, payload, user))
