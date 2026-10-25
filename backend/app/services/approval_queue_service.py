from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import today_in
from app.models.approval import ApprovalStep
from app.models.enums import ApprovalDocumentType, ApprovalStepStatus
from app.models.role import Role
from app.models.user import User
from app.schemas.approval import ApprovalStepRead, ApprovalTimelineStep, QueueItem
from app.schemas.person import PersonRead
from app.services import approval_adapters
from app.services.approval_engine import ApprovalSubject, adapter_for, evaluate_actor, latest_round_steps
from app.services.company_settings_service import get_company_settings


async def timeline(db: AsyncSession, steps: list[ApprovalStep]) -> list[ApprovalTimelineStep]:
    """Steps with the names a screen shows: who may decide each one and who did (and for whom)."""
    role_ids = {step.approver_role_id for step in steps if step.approver_role_id is not None}
    user_ids = {step.decided_by for step in steps if step.decided_by is not None}
    user_ids |= {step.on_behalf_of for step in steps if step.on_behalf_of is not None}
    roles = {role.id: role for role in (await db.execute(select(Role).where(Role.id.in_(role_ids)))).scalars()}
    people = {user.id: user for user in (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars()}

    def person(user_id: int | None) -> PersonRead | None:
        user = people.get(user_id) if user_id is not None else None
        return None if user is None else PersonRead(id=user.id, full_name=user.full_name)

    result = []
    for step in steps:
        if step.approver_role_id is not None:
            role = roles.get(step.approver_role_id)
            label = role.name.replace("_", " ") if role else "Approver"
        else:
            label = f"Anyone with the '{step.required_permission}' permission"
        result.append(
            ApprovalTimelineStep(
                **ApprovalStepRead.model_validate(step).model_dump(),
                approver_label=label,
                decided_by_person=person(step.decided_by),
                on_behalf_of_person=person(step.on_behalf_of),
            )
        )
    return result


def _po_id(subject: ApprovalSubject) -> int | None:
    if subject.document_type == ApprovalDocumentType.PURCHASE_ORDER:
        return int(subject.document.id)
    if subject.document_type == ApprovalDocumentType.PURCHASE_ORDER_AMENDMENT:
        return int(subject.document[1].id)
    return None


async def _current_pending_steps(db: AsyncSession) -> list[ApprovalStep]:
    """For each document, the step it is waiting on: its lowest-numbered pending step."""
    pending = (
        (
            await db.execute(
                select(ApprovalStep)
                .where(ApprovalStep.status == ApprovalStepStatus.PENDING)
                .order_by(ApprovalStep.document_type, ApprovalStep.document_id, ApprovalStep.step_order)
            )
        )
        .scalars()
        .all()
    )
    current: dict[tuple[ApprovalDocumentType, int], ApprovalStep] = {}
    for step in pending:
        current.setdefault((step.document_type, step.document_id), step)
    return list(current.values())


async def queue_for(db: AsyncSession, user: User) -> list[QueueItem]:
    """Everything waiting for ``user``'s decision, in their own right or as a delegate, oldest first.

    This is the single definition of "my approvals": the queue page, the sidebar badge and the dashboard card all
    use it, and it applies the same eligibility rules as the decision endpoints, so it never lists something the
    user would be refused.
    """
    settings = await get_company_settings(db)
    today = today_in(settings.timezone)
    items: list[QueueItem] = []
    for step in await _current_pending_steps(db):
        subject = await approval_adapters.subject_by_id(db, step.document_type, step.document_id)
        if subject is None:
            continue
        try:
            await adapter_for(step.document_type).ensure_decidable(subject)
        except HTTPException:
            continue  # the document moved on without this step being closed; nothing to decide
        steps = await latest_round_steps(db, step.document_type, step.document_id)
        earlier = [candidate for candidate in steps if candidate.step_order < step.step_order]
        verdict = await evaluate_actor(db, user, step, subject, earlier, today, settings.base_currency_code)
        if not verdict.allowed:
            continue
        items.append(
            QueueItem(
                document_type=step.document_type,
                document_id=step.document_id,
                po_id=_po_id(subject),
                label=subject.label,
                title=subject.title,
                amount_base=step.amount_base,
                requester=PersonRead(id=subject.owner_id, full_name=subject.owner_name),
                submitted_at=subject.submitted_at or step.created_at,
                step_order=step.step_order,
                steps_total=len(steps),
                rule_name=step.rule_name,
                on_behalf_of=None
                if verdict.on_behalf_of is None
                else PersonRead(id=verdict.on_behalf_of.id, full_name=verdict.on_behalf_of.full_name),
            )
        )
    return sorted(items, key=lambda item: (item.submitted_at, item.document_id))
