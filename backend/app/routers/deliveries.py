from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser, DbSession
from app.core.pagination import paginate
from app.models.delivery import Delivery
from app.schemas.common import PaginatedResponse
from app.schemas.delivery import DeliveryRead

router = APIRouter(prefix="/deliveries", tags=["deliveries"])


@router.get("", response_model=PaginatedResponse[DeliveryRead])
async def list_deliveries(
    db: DbSession,
    _: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[DeliveryRead]:
    stmt = select(Delivery).options(selectinload(Delivery.purchase_order)).order_by(Delivery.created_at.desc())
    return await paginate(db, stmt, page, page_size, DeliveryRead)
