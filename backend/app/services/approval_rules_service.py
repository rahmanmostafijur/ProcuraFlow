from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.approval import ApprovalRule, ApprovalRuleStep
from app.models.enums import ApprovalDocumentType
from app.models.role import Role
from app.models.user import User
from app.schemas.approval import ApprovalRuleCreate, ApprovalRuleStepWrite, ApprovalRuleUpdate
from app.services.audit_service import record_audit_event

# The permission that makes someone an approver of each kind of document when no approval rule applies: such a
# document gets one open step that anyone holding the permission may decide.
APPROVE_PERMISSION: dict[ApprovalDocumentType, str] = {
    ApprovalDocumentType.PURCHASE_REQUEST: "request:approve",
    ApprovalDocumentType.PURCHASE_ORDER: "po:approve",
    ApprovalDocumentType.PURCHASE_ORDER_AMENDMENT: "po:approve",
    ApprovalDocumentType.INVOICE_EXCEPTION: "invoice:approve",
}

_RULE_LOAD = (selectinload(ApprovalRule.steps),)


async def _load_rule(db: AsyncSession, rule_id: int) -> ApprovalRule:
    rule = await db.scalar(
        select(ApprovalRule)
        .options(*_RULE_LOAD)
        .where(ApprovalRule.id == rule_id)
        .execution_options(populate_existing=True)
    )
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval rule not found")
    return rule


async def list_rules(db: AsyncSession, document_type: ApprovalDocumentType | None = None) -> list[ApprovalRule]:
    stmt = (
        select(ApprovalRule)
        .options(*_RULE_LOAD)
        .order_by(ApprovalRule.document_type, ApprovalRule.min_amount, ApprovalRule.id)
    )
    if document_type is not None:
        stmt = stmt.where(ApprovalRule.document_type == document_type)
    return list((await db.execute(stmt)).scalars().all())


async def _validate_steps(db: AsyncSession, steps: list[ApprovalRuleStepWrite]) -> None:
    """Every step must name a role that exists. The rule itself is what gives that role authority at the step."""
    role_ids = {step.approver_role_id for step in steps}
    found = set((await db.execute(select(Role.id).where(Role.id.in_(role_ids)))).scalars())
    missing = sorted(role_ids - found)
    if missing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown role ids: {missing}")


def _bands_overlap(
    first_min: Decimal, first_max: Decimal | None, second_min: Decimal, second_max: Decimal | None
) -> bool:
    """Do the half-open bands [min, max) share any amount? An empty maximum means no upper limit."""
    first_below_second_end = second_max is None or first_min < second_max
    second_below_first_end = first_max is None or second_min < first_max
    return first_below_second_end and second_below_first_end


async def _ensure_no_overlap(
    db: AsyncSession,
    document_type: ApprovalDocumentType,
    min_amount: Decimal,
    max_amount: Decimal | None,
    exclude_id: int | None,
) -> None:
    others = await list_rules(db, document_type)
    for other in others:
        if other.id == exclude_id or not other.is_active:
            continue
        if _bands_overlap(min_amount, max_amount, other.min_amount, other.max_amount):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This amount range overlaps the active rule '{other.name}'; ranges must not overlap",
            )


def _steps(rule_steps: list[ApprovalRuleStepWrite]) -> list[ApprovalRuleStep]:
    return [
        ApprovalRuleStep(step_order=index, approver_role_id=step.approver_role_id)
        for index, step in enumerate(rule_steps, start=1)
    ]


async def create_rule(db: AsyncSession, payload: ApprovalRuleCreate, user: User) -> ApprovalRule:
    await _validate_steps(db, payload.steps)
    if payload.is_active:
        await _ensure_no_overlap(db, payload.document_type, payload.min_amount, payload.max_amount, None)
    rule = ApprovalRule(
        name=payload.name,
        document_type=payload.document_type,
        min_amount=payload.min_amount,
        max_amount=payload.max_amount,
        is_active=payload.is_active,
    )
    rule.steps = _steps(payload.steps)
    db.add(rule)
    await db.flush()
    await record_audit_event(
        db,
        user_id=user.id,
        action="approval_rule_created",
        entity_type="approval_rule",
        entity_id=rule.id,
        extra_data={
            "name": rule.name,
            "document_type": rule.document_type.value,
            "min_amount": str(rule.min_amount),
            "max_amount": None if rule.max_amount is None else str(rule.max_amount),
            "roles": [step.approver_role_id for step in rule.steps],
        },
    )
    await db.commit()
    return await _load_rule(db, rule.id)


async def update_rule(db: AsyncSession, rule_id: int, payload: ApprovalRuleUpdate, user: User) -> ApprovalRule:
    rule = await _load_rule(db, rule_id)
    update_data = payload.model_dump(exclude_unset=True)
    steps = update_data.pop("steps", None)
    for field in ("name", "min_amount", "is_active"):
        if field in update_data and update_data[field] is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"'{field}' cannot be empty")

    new_min = update_data.get("min_amount", rule.min_amount)
    new_max = update_data.get("max_amount", rule.max_amount)
    if new_max is not None and new_max <= new_min:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The upper limit must be greater than the lower limit",
        )
    if update_data.get("is_active", rule.is_active):
        await _ensure_no_overlap(db, rule.document_type, new_min, new_max, rule.id)
    if steps is not None:
        step_writes = [ApprovalRuleStepWrite(**step) for step in steps]
        await _validate_steps(db, step_writes)

    for field, value in update_data.items():
        setattr(rule, field, value)
    if steps is not None:
        rule.steps.clear()
        # Remove the old steps first so the new ones do not collide with them on (rule, step order).
        await db.flush()
        rule.steps = _steps(step_writes)
    await record_audit_event(
        db,
        user_id=user.id,
        action="approval_rule_updated",
        entity_type="approval_rule",
        entity_id=rule.id,
        extra_data={
            "fields": sorted(update_data),
            "roles": None if steps is None else [step["approver_role_id"] for step in steps],
        },
    )
    await db.commit()
    return await _load_rule(db, rule_id)


async def delete_rule(db: AsyncSession, rule_id: int, user: User) -> None:
    rule = await _load_rule(db, rule_id)
    # Steps already created from the rule keep its name; they only lose the link.
    await record_audit_event(
        db,
        user_id=user.id,
        action="approval_rule_deleted",
        entity_type="approval_rule",
        entity_id=rule.id,
        extra_data={"name": rule.name, "document_type": rule.document_type.value},
    )
    await db.delete(rule)
    await db.commit()


async def match_rule(
    db: AsyncSession, document_type: ApprovalDocumentType, amount_base: Decimal
) -> ApprovalRule | None:
    """The active rule whose band contains the amount, or ``None`` when no rule applies."""
    for rule in await list_rules(db, document_type):
        if not rule.is_active or amount_base < rule.min_amount:
            continue
        if rule.max_amount is None or amount_base < rule.max_amount:
            return rule
    return None
