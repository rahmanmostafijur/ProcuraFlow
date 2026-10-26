from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.deps import DbSession, require_permission
from app.core.pagination import paginate_mapped
from app.models.enums import PaymentRunStatus
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.payment import PaymentRunCreate, PaymentRunRead
from app.services import payment_run_service as service

router = APIRouter(prefix="/payment-runs", tags=["payment-runs"])

RequireInvoiceRead = Annotated[User, Depends(require_permission("invoice:read"))]
RequirePaymentWrite = Annotated[User, Depends(require_permission("payment:write"))]
RequirePaymentRelease = Annotated[User, Depends(require_permission("payment:release"))]


@router.get("", response_model=PaginatedResponse[PaymentRunRead])
async def list_runs(
    db: DbSession,
    _: RequireInvoiceRead,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Annotated[PaymentRunStatus | None, Query(alias="status")] = None,
) -> PaginatedResponse[PaymentRunRead]:
    return await paginate_mapped(db, service.list_statement(status_filter), page, page_size, service.to_read)


@router.post("", response_model=PaymentRunRead, status_code=status.HTTP_201_CREATED)
async def create_run(payload: PaymentRunCreate, db: DbSession, user: RequirePaymentWrite) -> PaymentRunRead:
    """Group approved invoices (one currency, none already in an open run) into a draft run."""
    return service.to_read(await service.create_run(db, payload, user))


@router.get("/{run_id}", response_model=PaymentRunRead)
async def get_run(run_id: int, db: DbSession, _: RequireInvoiceRead) -> PaymentRunRead:
    return service.to_read(await service.get_run(db, run_id))


@router.post("/{run_id}/release", response_model=PaymentRunRead)
async def release_run(run_id: int, db: DbSession, user: RequirePaymentRelease) -> PaymentRunRead:
    """Pay every invoice in the run. Someone other than the person who created the run must do this."""
    return service.to_read(await service.release_run(db, run_id, user))


@router.post("/{run_id}/cancel", response_model=PaymentRunRead)
async def cancel_run(run_id: int, db: DbSession, user: RequirePaymentWrite) -> PaymentRunRead:
    return service.to_read(await service.cancel_run(db, run_id, user))
