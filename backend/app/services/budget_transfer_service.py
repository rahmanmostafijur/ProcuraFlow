from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import has_permission
from app.models.budget import Budget, BudgetTransfer
from app.models.enums import BudgetChangeType, BudgetTransferStatus
from app.models.user import User
from app.schemas.budget import TransferCreate, TransferRead
from app.schemas.common import format_money
from app.schemas.person import PersonRead
from app.services import metrics_service
from app.services.audit_service import record_audit_event
from app.services.budget_service import get_budget_or_404, record_change
from app.services.company_settings_service import get_company_settings

MANAGE_PERMISSION = "budget:manage"

_TRANSFER_LOAD = (
    selectinload(BudgetTransfer.from_budget).selectinload(Budget.cost_centre),
    selectinload(BudgetTransfer.to_budget).selectinload(Budget.cost_centre),
)


def _label(budget: Budget) -> str:
    return f"{budget.cost_centre.code} FY{budget.fiscal_year}"


async def _remaining(db: AsyncSession, budget: Budget) -> Decimal:
    settings = await get_company_settings(db)
    context = metrics_service.MetricsContext.from_settings(settings)
    positions = await metrics_service.budget_positions(db, context, budget.fiscal_year, budget.cost_centre_id)
    return positions[0].remaining if positions else budget.amount


async def _ensure_enough_left(db: AsyncSession, source: Budget, amount: Decimal) -> None:
    """Only budget that is not already spent or committed can be moved away."""
    remaining = await _remaining(db, source)
    if amount > remaining:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Only {format_money(max(remaining, Decimal(0)))} of {_label(source)} is unspent and uncommitted, "
                f"so {format_money(amount)} cannot be moved."
            ),
        )


async def _person(db: AsyncSession, user_id: int | None) -> PersonRead | None:
    if user_id is None:
        return None
    user = await db.get(User, user_id)
    return None if user is None else PersonRead.model_validate(user)


async def to_read(db: AsyncSession, transfer: BudgetTransfer) -> TransferRead:
    requested_by = await _person(db, transfer.requested_by)
    assert requested_by is not None  # noqa: S101 - the column is a non-null foreign key
    return TransferRead(
        id=transfer.id,
        from_budget_id=transfer.from_budget_id,
        to_budget_id=transfer.to_budget_id,
        from_label=_label(transfer.from_budget),
        to_label=_label(transfer.to_budget),
        amount=transfer.amount,
        reason=transfer.reason,
        status=transfer.status,
        requested_by=requested_by,
        decided_by=await _person(db, transfer.decided_by),
        decided_at=transfer.decided_at,
        decision_comment=transfer.decision_comment,
        created_at=transfer.created_at,
    )


async def _load(db: AsyncSession, transfer_id: int) -> BudgetTransfer:
    transfer = await db.scalar(
        select(BudgetTransfer)
        .options(*_TRANSFER_LOAD)
        .where(BudgetTransfer.id == transfer_id)
        .execution_options(populate_existing=True)
    )
    if transfer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget transfer not found")
    return transfer


async def list_transfers(db: AsyncSession, viewer: User) -> list[TransferRead]:
    """Finance sees every transfer; anyone else sees only the ones they asked for."""
    stmt = select(BudgetTransfer).options(*_TRANSFER_LOAD).order_by(BudgetTransfer.id.desc())
    if not has_permission(viewer, MANAGE_PERMISSION):
        stmt = stmt.where(BudgetTransfer.requested_by == viewer.id)
    return [await to_read(db, transfer) for transfer in (await db.execute(stmt)).scalars().all()]


async def get_transfer(db: AsyncSession, transfer_id: int, viewer: User) -> TransferRead:
    transfer = await _load(db, transfer_id)
    if transfer.requested_by != viewer.id and not has_permission(viewer, MANAGE_PERMISSION):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget transfer not found")
    return await to_read(db, transfer)


async def request_transfer(db: AsyncSession, payload: TransferCreate, requester: User) -> TransferRead:
    if payload.from_budget_id == payload.to_budget_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Choose two different budgets")
    source = await get_budget_or_404(db, payload.from_budget_id)
    target = await get_budget_or_404(db, payload.to_budget_id)
    if source.fiscal_year != target.fiscal_year:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Budget can only move within one fiscal year"
        )
    await _ensure_enough_left(db, source, payload.amount)

    transfer = BudgetTransfer(
        from_budget_id=source.id,
        to_budget_id=target.id,
        amount=payload.amount,
        reason=payload.reason,
        requested_by=requester.id,
    )
    db.add(transfer)
    await db.flush()
    await record_audit_event(
        db,
        user_id=requester.id,
        action="budget_transfer_requested",
        entity_type="budget_transfer",
        entity_id=transfer.id,
        extra_data={"from": source.id, "to": target.id, "amount": str(payload.amount), "reason": payload.reason},
    )
    await db.commit()
    return await to_read(db, await _load(db, transfer.id))


async def decide_transfer(
    db: AsyncSession, transfer_id: int, approve: bool, actor: User, comment: str | None
) -> TransferRead:
    transfer = await _load(db, transfer_id)
    if transfer.requested_by == actor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You cannot decide a budget transfer you requested."
        )
    if transfer.status != BudgetTransferStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"This transfer was already {transfer.status.value}"
        )

    if approve:
        # Lock both budgets in id order, so two transfers touching the same pair cannot deadlock.
        locked = {
            budget.id: budget
            for budget in (
                await db.execute(
                    select(Budget)
                    .where(Budget.id.in_({transfer.from_budget_id, transfer.to_budget_id}))
                    .order_by(Budget.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).scalars()
        }
        source, target = locked[transfer.from_budget_id], locked[transfer.to_budget_id]
        source_loaded = await _load(db, transfer_id)
        await _ensure_enough_left(db, source_loaded.from_budget, transfer.amount)
        old_source, old_target = source.amount, target.amount
        source.amount = old_source - transfer.amount
        target.amount = old_target + transfer.amount
        for budget, change_type, old, reason in (
            (source, BudgetChangeType.TRANSFER_OUT, old_source, transfer.reason),
            (target, BudgetChangeType.TRANSFER_IN, old_target, transfer.reason),
        ):
            record_change(
                db,
                budget=budget,
                change_type=change_type,
                old_amount=old,
                new_amount=budget.amount,
                reason=reason,
                user=actor,
                transfer_id=transfer.id,
            )
        transfer.status = BudgetTransferStatus.APPROVED
    else:
        transfer.status = BudgetTransferStatus.REJECTED
    transfer.decided_by = actor.id
    transfer.decided_at = datetime.now(UTC)
    transfer.decision_comment = comment
    await record_audit_event(
        db,
        user_id=actor.id,
        action="budget_transfer_approved" if approve else "budget_transfer_rejected",
        entity_type="budget_transfer",
        entity_id=transfer.id,
        extra_data={"amount": str(transfer.amount), "comment": comment},
    )
    await db.commit()
    return await to_read(db, await _load(db, transfer_id))
