from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.schemas.approval import DecisionRequest, RejectionRequest
from app.schemas.po_version import PurchaseOrderVersionRead
from app.services import approval_adapters  # noqa: F401 - registers the document adapters
from app.services import po_amendment_service as service
from app.services.po_version_reads import to_version_read

router = APIRouter(prefix="/po-amendments", tags=["purchase-orders"])


@router.post("/{version_id}/approve", response_model=PurchaseOrderVersionRead)
async def approve_amendment(
    version_id: int, db: DbSession, user: CurrentUser, payload: DecisionRequest | None = None
) -> PurchaseOrderVersionRead:
    """Decide the current approval step of an amendment that raises an order's total."""
    version = await service.decide_amendment(
        db, version_id, user, approve=True, comment=payload.comment if payload else None
    )
    return await to_version_read(db, version)


@router.post("/{version_id}/reject", response_model=PurchaseOrderVersionRead)
async def reject_amendment(
    version_id: int, payload: RejectionRequest, db: DbSession, user: CurrentUser
) -> PurchaseOrderVersionRead:
    version = await service.decide_amendment(db, version_id, user, approve=False, comment=payload.comment)
    return await to_version_read(db, version)


@router.post("/{version_id}/withdraw", response_model=PurchaseOrderVersionRead)
async def withdraw_amendment(version_id: int, db: DbSession, user: CurrentUser) -> PurchaseOrderVersionRead:
    return await to_version_read(db, await service.withdraw_amendment(db, version_id, user))
