"""Approvals for every kind of document: opening a round of steps and deciding them.

Documents (purchase requests, purchase orders, order amendments) are adapted to this engine through a small
interface in ``approval_adapters``. The engine owns the rules that must hold for all of them, in one place so no
endpoint can approve around them:

* nobody approves a document they created;
* nobody approves two steps of the same document;
* a step is decided by someone with the step's role (or, when no rule applied, the approve permission), directly or
  as the delegate of such a person;
* a user's approval limit caps the amount they may approve, and a delegate is capped by the delegator's limit;
* an approval that would break a blocking budget rule is refused.
"""

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Protocol

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.clock import today_in
from app.core.deps import has_permission
from app.models.approval import ApprovalStep
from app.models.enums import ApprovalDocumentType, ApprovalStepStatus
from app.models.role import Role
from app.models.user import User
from app.schemas.common import format_money
from app.services import approval_people_service, budget_service
from app.services.approval_rules_service import APPROVE_PERMISSION, match_rule
from app.services.audit_service import record_audit_event
from app.services.company_settings_service import get_company_settings

DOCUMENT_LABELS: dict[ApprovalDocumentType, str] = {
    ApprovalDocumentType.PURCHASE_REQUEST: "purchase requests",
    ApprovalDocumentType.PURCHASE_ORDER: "purchase orders",
    ApprovalDocumentType.PURCHASE_ORDER_AMENDMENT: "purchase order amendments",
    ApprovalDocumentType.INVOICE_EXCEPTION: "invoice exceptions",
}


@dataclass(frozen=True)
class ApprovalSubject:
    """What the engine needs to know about a document, whatever kind it is."""

    document_type: ApprovalDocumentType
    document_id: int
    owner_id: int
    owner_name: str
    noun: str
    label: str
    title: str
    submitted_at: datetime | None
    cost_centre_id: int | None
    document: Any
    # The amount in the base currency, needed to open a round (rules are matched on it). Later steps read it from
    # the step, which kept the value from when the round opened.
    amount_base: Decimal | None = None
    # What counts against the budget when this is approved; defaults to the step's amount.
    budget_amount_base: Decimal | None = None


class DocumentAdapter(Protocol):
    document_type: ApprovalDocumentType

    async def ensure_decidable(self, subject: ApprovalSubject) -> None:
        """Raise a 409 if the document is not in a state that can be approved or rejected."""

    async def base_amount(self, db: AsyncSession, subject: ApprovalSubject) -> Decimal:
        """The document's amount in the base currency, for documents that were submitted without an open round."""

    async def on_approved(self, db: AsyncSession, subject: ApprovalSubject, decider: User) -> None:
        """The last step was approved: move the document forward."""

    async def on_rejected(self, db: AsyncSession, subject: ApprovalSubject, decider: User, comment: str) -> None:
        """A step was rejected: send the document back or end it."""


_ADAPTERS: dict[ApprovalDocumentType, DocumentAdapter] = {}


def register_adapter(adapter: DocumentAdapter) -> None:
    _ADAPTERS[adapter.document_type] = adapter


def adapter_for(document_type: ApprovalDocumentType) -> DocumentAdapter:
    return _ADAPTERS[document_type]


@dataclass(frozen=True)
class DecisionOutcome:
    step: ApprovalStep
    is_final: bool


# --- steps -------------------------------------------------------------------------------------------------------


async def latest_round_steps(
    db: AsyncSession, document_type: ApprovalDocumentType, document_id: int
) -> list[ApprovalStep]:
    """The steps of the document's most recent approval round, in order (empty if it never had one)."""
    latest = (
        select(func.max(ApprovalStep.round))
        .where(ApprovalStep.document_type == document_type, ApprovalStep.document_id == document_id)
        .scalar_subquery()
    )
    stmt = (
        select(ApprovalStep)
        .where(
            ApprovalStep.document_type == document_type,
            ApprovalStep.document_id == document_id,
            ApprovalStep.round == latest,
        )
        .order_by(ApprovalStep.step_order)
        .execution_options(populate_existing=True)
    )
    return list((await db.execute(stmt)).scalars().all())


async def all_steps(db: AsyncSession, document_type: ApprovalDocumentType, document_id: int) -> list[ApprovalStep]:
    """Every step the document has had, oldest round first: the approval history."""
    stmt = (
        select(ApprovalStep)
        .where(ApprovalStep.document_type == document_type, ApprovalStep.document_id == document_id)
        .order_by(ApprovalStep.round, ApprovalStep.step_order)
    )
    return list((await db.execute(stmt)).scalars().all())


async def open_round(db: AsyncSession, subject: ApprovalSubject) -> list[ApprovalStep]:
    """Start a new round: copy the matching rule's steps, or one open step when no rule applies."""
    if subject.amount_base is None:
        raise ValueError("opening an approval round needs the document's base-currency amount")
    rule = await match_rule(db, subject.document_type, subject.amount_base)
    previous_round = await db.scalar(
        select(func.max(ApprovalStep.round)).where(
            ApprovalStep.document_type == subject.document_type, ApprovalStep.document_id == subject.document_id
        )
    )
    round_number = (previous_round or 0) + 1
    common = {
        "document_type": subject.document_type,
        "document_id": subject.document_id,
        "round": round_number,
        "amount_base": subject.amount_base,
    }
    if rule is None:
        steps = [ApprovalStep(**common, step_order=1, required_permission=APPROVE_PERMISSION[subject.document_type])]
    else:
        steps = [
            ApprovalStep(
                **common,
                step_order=rule_step.step_order,
                approver_role_id=rule_step.approver_role_id,
                rule_id=rule.id,
                rule_name=rule.name,
            )
            for rule_step in rule.steps
        ]
    db.add_all(steps)
    await db.flush()
    return steps


async def skip_open_steps(db: AsyncSession, document_type: ApprovalDocumentType, document_id: int) -> None:
    """The document was cancelled or withdrawn: its waiting steps will never be decided."""
    for step in await latest_round_steps(db, document_type, document_id):
        if step.status == ApprovalStepStatus.PENDING:
            step.status = ApprovalStepStatus.SKIPPED


# --- who may decide ----------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    # The person a delegate is deciding for; empty when the user decides in their own right.
    on_behalf_of: User | None = None
    reason: str | None = None


def _with_article(noun: str) -> str:
    return f"{'an' if noun[0] in 'aeiou' else 'a'} {noun}"


async def with_permissions(db: AsyncSession, user: User) -> User:
    """The user with their role and permissions loaded, fetching them only if they are not already there.

    The signed-in user always arrives loaded; this keeps the engine correct for a user object that did not.
    """
    if "role" not in sa_inspect(user).unloaded and "permissions" not in sa_inspect(user.role).unloaded:
        return user
    loaded = await db.scalar(
        select(User)
        .options(selectinload(User.role).selectinload(Role.permissions))
        .where(User.id == user.id)
        .execution_options(populate_existing=True)
    )
    assert loaded is not None  # noqa: S101 - the caller is a user that exists
    return loaded


async def _role_name(db: AsyncSession, role_id: int) -> str:
    role = await db.get(Role, role_id)
    return role.name.replace("_", " ") if role else "the required"


async def _why_not(
    db: AsyncSession,
    approver: User,
    step: ApprovalStep,
    subject: ApprovalSubject,
    earlier_steps: list[ApprovalStep],
    base_currency: str,
) -> str | None:
    """Why this person may not decide the step, or ``None`` if they may."""
    if approver.id == subject.owner_id:
        return f"You cannot approve {_with_article(subject.noun)} you created."
    if any(
        earlier.status == ApprovalStepStatus.APPROVED and approver.id in (earlier.decided_by, earlier.on_behalf_of)
        for earlier in earlier_steps
    ):
        return (
            f"You already approved an earlier step of this {subject.noun}; a different person must approve this step."
        )
    if step.approver_role_id is not None:
        if approver.role_id != step.approver_role_id:
            return f"This step needs someone with the {await _role_name(db, step.approver_role_id)} role."
    elif step.required_permission is not None and not has_permission(approver, step.required_permission):
        return f"You do not have the '{step.required_permission}' permission"
    limit = await approval_people_service.get_limit(db, approver.id, subject.document_type)
    if limit is not None and step.amount_base > limit:
        return (
            f"Your approval limit for {DOCUMENT_LABELS[subject.document_type]} is "
            f"{format_money(limit)} {base_currency}; this one is {format_money(step.amount_base)} {base_currency}."
        )
    return None


async def evaluate_actor(
    db: AsyncSession,
    actor: User,
    step: ApprovalStep,
    subject: ApprovalSubject,
    earlier_steps: list[ApprovalStep],
    today: date,
    base_currency: str,
) -> Verdict:
    """May ``actor`` decide ``step``, in their own right or as someone's delegate?

    Used by both the decision endpoints and the approvals queue, so the queue lists exactly what can be decided.
    """
    actor = await with_permissions(db, actor)
    own_reason = await _why_not(db, actor, step, subject, earlier_steps, base_currency)
    if own_reason is None:
        return Verdict(allowed=True)
    # The delegate must themselves be free to act: not the owner and not already on an earlier step.
    if actor.id == subject.owner_id or any(
        earlier.status == ApprovalStepStatus.APPROVED and actor.id in (earlier.decided_by, earlier.on_behalf_of)
        for earlier in earlier_steps
    ):
        return Verdict(allowed=False, reason=own_reason)
    for delegator in await approval_people_service.active_delegators(db, actor.id, today):
        if await _why_not(db, delegator, step, subject, earlier_steps, base_currency) is None:
            return Verdict(allowed=True, on_behalf_of=delegator)
    return Verdict(allowed=False, reason=own_reason)


# --- deciding ----------------------------------------------------------------------------------------------------


def _forbidden(reason: str | None) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason or "You cannot decide this step.")


async def decide(
    db: AsyncSession, subject: ApprovalSubject, actor: User, *, approve: bool, comment: str | None
) -> DecisionOutcome:
    """Record the actor's decision on the document's current step.

    The caller must have locked the document row first, so two people cannot decide the same step at once.
    Nothing is committed here: the caller commits, so a refused budget check or a missing exchange rate leaves
    the document exactly as it was.
    """
    adapter = adapter_for(subject.document_type)
    await adapter.ensure_decidable(subject)

    steps = await latest_round_steps(db, subject.document_type, subject.document_id)
    if not steps:
        # Submitted before approval rules existed: it gets its single open step now.
        amount_base = await adapter.base_amount(db, subject)
        steps = await open_round(db, replace(subject, amount_base=amount_base))
    step = next((candidate for candidate in steps if candidate.status == ApprovalStepStatus.PENDING), None)
    if step is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"Nothing is waiting for approval on this {subject.noun}."
        )

    settings = await get_company_settings(db)
    earlier = [candidate for candidate in steps if candidate.step_order < step.step_order]
    verdict = await evaluate_actor(
        db, actor, step, subject, earlier, today_in(settings.timezone), settings.base_currency_code
    )
    if not verdict.allowed:
        raise _forbidden(verdict.reason)

    if approve:
        budget_amount = subject.budget_amount_base if subject.budget_amount_base is not None else step.amount_base
        await budget_service.enforce_budget(db, subject.cost_centre_id, budget_amount)

    step.status = ApprovalStepStatus.APPROVED if approve else ApprovalStepStatus.REJECTED
    step.decided_by = actor.id
    step.on_behalf_of = verdict.on_behalf_of.id if verdict.on_behalf_of else None
    step.decided_at = datetime.now(UTC)
    step.comment = comment or None
    await record_audit_event(
        db,
        user_id=actor.id,
        action="approval_step_approved" if approve else "approval_step_rejected",
        entity_type=subject.document_type.value,
        entity_id=subject.document_id,
        extra_data={
            "step": step.step_order,
            "of": len(steps),
            "on_behalf_of": step.on_behalf_of,
            "comment": step.comment,
        },
    )

    waiting = [candidate for candidate in steps if candidate.status == ApprovalStepStatus.PENDING]
    if not approve:
        for candidate in waiting:
            candidate.status = ApprovalStepStatus.SKIPPED
        await adapter.on_rejected(db, subject, actor, comment or "")
        return DecisionOutcome(step=step, is_final=True)
    if waiting:
        return DecisionOutcome(step=step, is_final=False)

    budget_amount = subject.budget_amount_base if subject.budget_amount_base is not None else step.amount_base
    await budget_service.warn_if_near_limit(db, subject.cost_centre_id, budget_amount, subject.label, subject.owner_id)
    await adapter.on_approved(db, subject, actor)
    return DecisionOutcome(step=step, is_final=True)
