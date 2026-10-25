from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import CurrentUser, DbSession, require_permission
from app.models.budget import BudgetChange, CostCentre
from app.models.user import User
from app.schemas.budget import (
    BudgetChangeRead,
    BudgetPositionRead,
    BudgetUpsert,
    CostCentreCreate,
    CostCentreRead,
    CostCentreUpdate,
    TransferCreate,
    TransferDecision,
    TransferRead,
)
from app.services import budget_service, budget_transfer_service, metrics_service

router = APIRouter(tags=["budgets"])

RequireBudgetRead = Annotated[User, Depends(require_permission("budget:read"))]
RequireBudgetManage = Annotated[User, Depends(require_permission("budget:manage"))]
RequireTransferRequest = Annotated[User, Depends(require_permission("budget:request_transfer"))]


# Cost centres are plain reference data every requester needs to pick from, so any signed-in user may list them.
@router.get("/cost-centres", response_model=list[CostCentreRead])
async def list_cost_centres(db: DbSession, _: CurrentUser, active_only: bool = False) -> list[CostCentre]:
    return await budget_service.list_cost_centres(db, active_only)


@router.post("/cost-centres", response_model=CostCentreRead, status_code=status.HTTP_201_CREATED)
async def create_cost_centre(payload: CostCentreCreate, db: DbSession, user: RequireBudgetManage) -> CostCentre:
    return await budget_service.create_cost_centre(db, payload, user)


@router.patch("/cost-centres/{cost_centre_id}", response_model=CostCentreRead)
async def update_cost_centre(
    cost_centre_id: int, payload: CostCentreUpdate, db: DbSession, user: RequireBudgetManage
) -> CostCentre:
    return await budget_service.update_cost_centre(db, cost_centre_id, payload, user)


@router.get("/budgets", response_model=list[BudgetPositionRead])
async def list_budgets(
    db: DbSession, _: RequireBudgetRead, fiscal_year: Annotated[int | None, Query(ge=2000, le=2100)] = None
) -> list[BudgetPositionRead]:
    """Budget, spent, committed and remaining per cost centre for a fiscal year (this one by default)."""
    context = await metrics_service.get_context(db)
    positions = await metrics_service.budget_positions(db, context, fiscal_year or context.fiscal_year)
    return [BudgetPositionRead(**asdict(position)) for position in positions]


@router.put("/budgets", response_model=BudgetPositionRead)
async def set_budget(payload: BudgetUpsert, db: DbSession, user: RequireBudgetManage) -> BudgetPositionRead:
    budget = await budget_service.set_budget(db, payload, user)
    context = await metrics_service.get_context(db)
    [position] = await metrics_service.budget_positions(db, context, budget.fiscal_year, budget.cost_centre_id)
    return BudgetPositionRead(**asdict(position))


@router.get("/budgets/{budget_id}/history", response_model=list[BudgetChangeRead])
async def budget_history(budget_id: int, db: DbSession, _: RequireBudgetRead) -> list[BudgetChange]:
    return await budget_service.budget_history(db, budget_id)


@router.get("/budget-transfers", response_model=list[TransferRead])
async def list_transfers(db: DbSession, user: CurrentUser) -> list[TransferRead]:
    """Finance sees every transfer; anyone else sees only the ones they asked for."""
    return await budget_transfer_service.list_transfers(db, user)


@router.post("/budget-transfers", response_model=TransferRead, status_code=status.HTTP_201_CREATED)
async def request_transfer(payload: TransferCreate, db: DbSession, user: RequireTransferRequest) -> TransferRead:
    return await budget_transfer_service.request_transfer(db, payload, user)


@router.get("/budget-transfers/{transfer_id}", response_model=TransferRead)
async def get_transfer(transfer_id: int, db: DbSession, user: CurrentUser) -> TransferRead:
    return await budget_transfer_service.get_transfer(db, transfer_id, user)


@router.post("/budget-transfers/{transfer_id}/approve", response_model=TransferRead)
async def approve_transfer(
    transfer_id: int, db: DbSession, user: RequireBudgetManage, payload: TransferDecision | None = None
) -> TransferRead:
    comment = payload.comment if payload else None
    return await budget_transfer_service.decide_transfer(db, transfer_id, True, user, comment)


@router.post("/budget-transfers/{transfer_id}/reject", response_model=TransferRead)
async def reject_transfer(
    transfer_id: int, db: DbSession, user: RequireBudgetManage, payload: TransferDecision | None = None
) -> TransferRead:
    comment = payload.comment if payload else None
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Say why the transfer is being rejected"
        )
    return await budget_transfer_service.decide_transfer(db, transfer_id, False, user, comment)
