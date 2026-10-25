from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.budget import Budget, BudgetChange, CostCentre
from app.models.enums import BudgetChangeType
from app.models.notification import Notification
from app.models.user import User
from app.schemas.budget import BudgetUpsert, CostCentreCreate, CostCentreUpdate
from app.schemas.common import format_money
from app.services import metrics_service
from app.services.audit_service import current_values, field_changes, record_audit_event
from app.services.company_settings_service import get_company_settings


async def _ensure_active_user(db: AsyncSession, user_id: int) -> None:
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"User {user_id} not found or not active")


# --- cost centres ------------------------------------------------------------------------------------------------


async def list_cost_centres(db: AsyncSession, active_only: bool = False) -> list[CostCentre]:
    stmt = select(CostCentre).order_by(CostCentre.code)
    if active_only:
        stmt = stmt.where(CostCentre.is_active.is_(True))
    return list((await db.execute(stmt)).scalars().all())


async def get_active_cost_centre(db: AsyncSession, cost_centre_id: int) -> CostCentre:
    cost_centre = await db.get(CostCentre, cost_centre_id)
    if cost_centre is None or not cost_centre.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cost centre {cost_centre_id} not found or not active"
        )
    return cost_centre


async def create_cost_centre(db: AsyncSession, payload: CostCentreCreate, user: User) -> CostCentre:
    if payload.manager_id is not None:
        await _ensure_active_user(db, payload.manager_id)
    cost_centre = CostCentre(code=payload.code, name=payload.name, manager_id=payload.manager_id)
    db.add(cost_centre)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"A cost centre with code '{payload.code}' already exists"
        ) from exc
    await record_audit_event(
        db,
        user_id=user.id,
        action="cost_centre_created",
        entity_type="cost_centre",
        entity_id=cost_centre.id,
        extra_data={"code": cost_centre.code},
    )
    await db.commit()
    await db.refresh(cost_centre)
    return cost_centre


async def update_cost_centre(
    db: AsyncSession, cost_centre_id: int, payload: CostCentreUpdate, user: User
) -> CostCentre:
    cost_centre = await db.get(CostCentre, cost_centre_id)
    if cost_centre is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cost centre not found")
    update_data = payload.model_dump(exclude_unset=True)
    for field in ("name", "is_active"):
        if field in update_data and update_data[field] is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"'{field}' cannot be empty")
    if update_data.get("manager_id") is not None:
        await _ensure_active_user(db, update_data["manager_id"])
    changes = field_changes(current_values(cost_centre, update_data), update_data)
    for field, value in update_data.items():
        setattr(cost_centre, field, value)
    if changes:
        await record_audit_event(
            db,
            user_id=user.id,
            action="cost_centre_updated",
            entity_type="cost_centre",
            entity_id=cost_centre.id,
            extra_data={"changes": changes},
        )
    await db.commit()
    await db.refresh(cost_centre)
    return cost_centre


# --- budgets -----------------------------------------------------------------------------------------------------


def record_change(
    db: AsyncSession,
    *,
    budget: Budget,
    change_type: BudgetChangeType,
    old_amount: Decimal | None,
    new_amount: Decimal,
    reason: str | None,
    user: User,
    transfer_id: int | None = None,
) -> None:
    """Every change to a budget amount leaves a history entry saying what, by whom and why."""
    db.add(
        BudgetChange(
            budget_id=budget.id,
            change_type=change_type,
            old_amount=old_amount,
            new_amount=new_amount,
            reason=reason,
            transfer_id=transfer_id,
            changed_by=user.id,
        )
    )


async def set_budget(db: AsyncSession, payload: BudgetUpsert, user: User) -> Budget:
    await get_active_cost_centre(db, payload.cost_centre_id)
    budget = await db.scalar(
        select(Budget)
        .where(Budget.cost_centre_id == payload.cost_centre_id, Budget.fiscal_year == payload.fiscal_year)
        .with_for_update()
    )
    if budget is None:
        budget = Budget(cost_centre_id=payload.cost_centre_id, fiscal_year=payload.fiscal_year, amount=payload.amount)
        db.add(budget)
        await db.flush()
        record_change(
            db,
            budget=budget,
            change_type=BudgetChangeType.CREATED,
            old_amount=None,
            new_amount=payload.amount,
            reason=payload.reason,
            user=user,
        )
        action = "budget_created"
        old = None
    else:
        old = budget.amount
        if old == payload.amount:
            return budget
        budget.amount = payload.amount
        record_change(
            db,
            budget=budget,
            change_type=BudgetChangeType.ADJUSTED,
            old_amount=old,
            new_amount=payload.amount,
            reason=payload.reason,
            user=user,
        )
        action = "budget_adjusted"
    await record_audit_event(
        db,
        user_id=user.id,
        action=action,
        entity_type="budget",
        entity_id=budget.id,
        extra_data={
            "cost_centre_id": payload.cost_centre_id,
            "fiscal_year": payload.fiscal_year,
            "from": None if old is None else str(old),
            "to": str(payload.amount),
            "reason": payload.reason,
        },
    )
    await db.commit()
    await db.refresh(budget)
    return budget


async def get_budget_or_404(db: AsyncSession, budget_id: int) -> Budget:
    budget = await db.scalar(select(Budget).options(selectinload(Budget.cost_centre)).where(Budget.id == budget_id))
    if budget is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    return budget


async def budget_history(db: AsyncSession, budget_id: int) -> list[BudgetChange]:
    await get_budget_or_404(db, budget_id)
    stmt = select(BudgetChange).where(BudgetChange.budget_id == budget_id).order_by(BudgetChange.id.desc())
    return list((await db.execute(stmt)).scalars().all())


# --- the budget rules applied to approvals -----------------------------------------------------------------------


async def enforce_budget(db: AsyncSession, cost_centre_id: int | None, amount_base: Decimal) -> None:
    """Refuse an approval that would put the cost centre over its budget, when the company blocks that.

    Called from the approval engine for every approval, so no endpoint can approve around it. A cost centre with no
    budget for the current fiscal year is not limited.
    """
    settings = await get_company_settings(db)
    if cost_centre_id is None or not settings.budget_block_over_budget:
        return
    context = metrics_service.MetricsContext.from_settings(settings)
    positions = await metrics_service.budget_positions(db, context, context.fiscal_year, cost_centre_id)
    if not positions:
        return
    position = positions[0]
    if amount_base > position.remaining:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"This cannot be approved: it would put {position.cost_centre_name} over its "
                f"FY{position.fiscal_year} budget. {format_money(position.remaining)} {context.base_currency_code} "
                f"is left and this needs {format_money(amount_base)}."
            ),
        )


async def warn_if_near_limit(
    db: AsyncSession, cost_centre_id: int | None, amount_base: Decimal, label: str, owner_id: int
) -> None:
    """Tell the cost centre's manager (and the document's owner) when an approval takes it past the warning level."""
    if cost_centre_id is None:
        return
    settings = await get_company_settings(db)
    context = metrics_service.MetricsContext.from_settings(settings)
    positions = await metrics_service.budget_positions(db, context, context.fiscal_year, cost_centre_id)
    if not positions:
        return
    position = positions[0]
    if position.budget <= 0:
        return
    used_after = position.spent + position.committed + amount_base
    share = used_after * Decimal(100) / position.budget
    if share < settings.budget_warn_percent:
        return
    recipients = {owner_id}
    cost_centre = await db.get(CostCentre, cost_centre_id)
    if cost_centre is not None and cost_centre.manager_id is not None:
        recipients.add(cost_centre.manager_id)
    message = (
        f"{label} takes {position.cost_centre_name} to {share:.0f}% of its FY{position.fiscal_year} budget "
        f"({format_money(position.budget - used_after)} {context.base_currency_code} left)."
    )
    db.add_all(Notification(user_id=user_id, message=message[:500]) for user_id in sorted(recipients))
