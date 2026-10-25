from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.deps import CurrentUser, DbSession, require_permission
from app.core.pagination import paginate
from app.models.enums import PurchaseRequestStatus
from app.models.purchase_request import PurchaseRequest
from app.models.user import User
from app.schemas.approval import DecisionRequest, RejectionRequest
from app.schemas.common import PaginatedResponse
from app.schemas.purchase_request import (
    ConvertRequest,
    ConvertResult,
    PurchaseRequestCreate,
    PurchaseRequestRead,
    PurchaseRequestUpdate,
)
from app.services import purchase_request_service as service
from app.services.request_conversion_service import convert_request

router = APIRouter(prefix="/purchase-requests", tags=["purchase-requests"])

RequireRequestCreate = Annotated[User, Depends(require_permission("request:create"))]
RequirePOCreate = Annotated[User, Depends(require_permission("po:create"))]


@router.get("", response_model=PaginatedResponse[PurchaseRequestRead])
async def list_requests(
    db: DbSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Annotated[PurchaseRequestStatus | None, Query(alias="status")] = None,
    mine: bool = False,
) -> PaginatedResponse[PurchaseRequestRead]:
    """Your own requests; people who see every request get all of them unless they ask for ``mine``."""
    stmt = service.scoped_list_statement(user, status_filter, mine)
    return await paginate(db, stmt, page, page_size, PurchaseRequestRead)


@router.post("", response_model=PurchaseRequestRead, status_code=status.HTTP_201_CREATED)
async def create_request(payload: PurchaseRequestCreate, db: DbSession, user: RequireRequestCreate) -> PurchaseRequest:
    return await service.create_request(db, payload, user)


@router.get("/{request_id}", response_model=PurchaseRequestRead)
async def get_request(request_id: int, db: DbSession, user: CurrentUser) -> PurchaseRequest:
    return await service.get_request(db, request_id, user)


@router.patch("/{request_id}", response_model=PurchaseRequestRead)
async def update_request(
    request_id: int, payload: PurchaseRequestUpdate, db: DbSession, user: RequireRequestCreate
) -> PurchaseRequest:
    return await service.update_request(db, request_id, payload, user)


@router.post("/{request_id}/submit", response_model=PurchaseRequestRead)
async def submit_request(request_id: int, db: DbSession, user: RequireRequestCreate) -> PurchaseRequest:
    return await service.submit_request(db, request_id, user)


@router.post("/{request_id}/cancel", response_model=PurchaseRequestRead)
async def cancel_request(request_id: int, db: DbSession, user: RequireRequestCreate) -> PurchaseRequest:
    return await service.cancel_request(db, request_id, user)


@router.post("/{request_id}/approve", response_model=PurchaseRequestRead)
async def approve_request(
    request_id: int, db: DbSession, user: CurrentUser, payload: DecisionRequest | None = None
) -> PurchaseRequest:
    comment = payload.comment if payload else None
    return await service.decide_request(db, request_id, user, approve=True, comment=comment)


@router.post("/{request_id}/reject", response_model=PurchaseRequestRead)
async def reject_request(
    request_id: int, payload: RejectionRequest, db: DbSession, user: CurrentUser
) -> PurchaseRequest:
    return await service.decide_request(db, request_id, user, approve=False, comment=payload.comment)


@router.post("/{request_id}/convert", response_model=ConvertResult)
async def convert(request_id: int, payload: ConvertRequest, db: DbSession, user: RequirePOCreate) -> ConvertResult:
    """Turn an approved request into draft purchase orders (one per supplier)."""
    po_ids = await convert_request(db, request_id, payload, user)
    request = await service.get_request(db, request_id, user)
    return ConvertResult(purchase_order_ids=po_ids, request=PurchaseRequestRead.model_validate(request))
