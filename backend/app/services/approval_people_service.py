"""Who may decide what: per-user approval limits and delegation while someone is away."""

from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.clock import today_in
from app.core.deps import has_permission
from app.models.approval import ApprovalDelegation, ApprovalLimit
from app.models.enums import ApprovalDocumentType
from app.models.role import Role
from app.models.user import User
from app.schemas.approval import ApprovalLimitWrite, DelegationCreate
from app.services.audit_service import record_audit_event
from app.services.company_settings_service import get_company_settings

MANAGE_PERMISSION = "approval:manage"
_USER_WITH_ROLE = selectinload(User.role).selectinload(Role.permissions)


def _can_manage(user: User) -> bool:
    return has_permission(user, MANAGE_PERMISSION)


async def _load_user(db: AsyncSession, user_id: int) -> User:
    user = await db.scalar(select(User).options(_USER_WITH_ROLE).where(User.id == user_id))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"User {user_id} not found or not active")
    return user


# --- approval limits ---------------------------------------------------------------------------------------------


async def get_limit(db: AsyncSession, user_id: int, document_type: ApprovalDocumentType) -> Decimal | None:
    """The user's limit for this kind of document in the base currency; ``None`` means no limit."""
    result = await db.execute(
        select(ApprovalLimit.max_amount).where(
            ApprovalLimit.user_id == user_id, ApprovalLimit.document_type == document_type
        )
    )
    return result.scalar_one_or_none()


async def list_limits(db: AsyncSession, viewer: User) -> list[ApprovalLimit]:
    """Everyone's limits for people who manage approvals; otherwise only the viewer's own."""
    stmt = select(ApprovalLimit).order_by(ApprovalLimit.user_id, ApprovalLimit.document_type)
    if not _can_manage(viewer):
        stmt = stmt.where(ApprovalLimit.user_id == viewer.id)
    return list((await db.execute(stmt)).scalars().all())


async def set_limit(db: AsyncSession, payload: ApprovalLimitWrite, actor: User) -> ApprovalLimit:
    await _load_user(db, payload.user_id)
    limit = await db.scalar(
        select(ApprovalLimit).where(
            ApprovalLimit.user_id == payload.user_id, ApprovalLimit.document_type == payload.document_type
        )
    )
    previous = None if limit is None else str(limit.max_amount)
    if limit is None:
        limit = ApprovalLimit(
            user_id=payload.user_id,
            document_type=payload.document_type,
            max_amount=payload.max_amount,
            updated_by=actor.id,
        )
        db.add(limit)
    else:
        limit.max_amount = payload.max_amount
        limit.updated_by = actor.id
    await db.flush()
    await record_audit_event(
        db,
        user_id=actor.id,
        action="approval_limit_set",
        entity_type="user",
        entity_id=payload.user_id,
        extra_data={
            "document_type": payload.document_type.value,
            "from": previous,
            "to": str(payload.max_amount),
        },
    )
    await db.commit()
    await db.refresh(limit)
    return limit


async def delete_limit(db: AsyncSession, limit_id: int, actor: User) -> None:
    limit = await db.get(ApprovalLimit, limit_id)
    if limit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval limit not found")
    await record_audit_event(
        db,
        user_id=actor.id,
        action="approval_limit_removed",
        entity_type="user",
        entity_id=limit.user_id,
        extra_data={"document_type": limit.document_type.value, "was": str(limit.max_amount)},
    )
    await db.delete(limit)
    await db.commit()


# --- delegation --------------------------------------------------------------------------------------------------


async def active_delegators(db: AsyncSession, delegate_id: int, on_day: date) -> list[User]:
    """Active people who have delegated their approvals to this user for ``on_day`` (with role and permissions)."""
    stmt = (
        select(User)
        .options(_USER_WITH_ROLE)
        .join(ApprovalDelegation, ApprovalDelegation.delegator_id == User.id)
        .where(
            ApprovalDelegation.delegate_id == delegate_id,
            ApprovalDelegation.revoked_at.is_(None),
            ApprovalDelegation.starts_on <= on_day,
            ApprovalDelegation.ends_on >= on_day,
            User.is_active.is_(True),
        )
        .distinct()
    )
    return list((await db.execute(stmt)).scalars().all())


async def list_delegations(db: AsyncSession, viewer: User) -> list[ApprovalDelegation]:
    """Everyone's delegations for people who manage approvals; otherwise those the viewer gave or received."""
    stmt = select(ApprovalDelegation).options(
        selectinload(ApprovalDelegation.delegator), selectinload(ApprovalDelegation.delegate)
    )
    if not _can_manage(viewer):
        stmt = stmt.where(
            or_(ApprovalDelegation.delegator_id == viewer.id, ApprovalDelegation.delegate_id == viewer.id)
        )
    return list(
        (await db.execute(stmt.order_by(ApprovalDelegation.starts_on.desc(), ApprovalDelegation.id.desc()))).scalars()
    )


async def create_delegation(db: AsyncSession, payload: DelegationCreate, actor: User) -> ApprovalDelegation:
    delegator_id = actor.id
    if payload.delegator_id is not None and payload.delegator_id != actor.id:
        if not _can_manage(actor):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="You can only delegate your own approvals"
            )
        delegator_id = payload.delegator_id
    if payload.delegate_id == delegator_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="You cannot delegate to yourself")
    await _load_user(db, delegator_id)
    await _load_user(db, payload.delegate_id)
    settings = await get_company_settings(db)
    if payload.ends_on < today_in(settings.timezone):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="The delegation has already ended"
        )

    delegation = ApprovalDelegation(
        delegator_id=delegator_id,
        delegate_id=payload.delegate_id,
        starts_on=payload.starts_on,
        ends_on=payload.ends_on,
        created_by=actor.id,
    )
    db.add(delegation)
    await db.flush()
    await record_audit_event(
        db,
        user_id=actor.id,
        action="approval_delegation_created",
        entity_type="user",
        entity_id=delegator_id,
        extra_data={
            "delegate_id": payload.delegate_id,
            "starts_on": payload.starts_on.isoformat(),
            "ends_on": payload.ends_on.isoformat(),
        },
    )
    await db.commit()
    return await _get_delegation(db, delegation.id)


async def _get_delegation(db: AsyncSession, delegation_id: int) -> ApprovalDelegation:
    delegation = await db.scalar(
        select(ApprovalDelegation)
        .options(selectinload(ApprovalDelegation.delegator), selectinload(ApprovalDelegation.delegate))
        .where(ApprovalDelegation.id == delegation_id)
        .execution_options(populate_existing=True)
    )
    if delegation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delegation not found")
    return delegation


async def revoke_delegation(db: AsyncSession, delegation_id: int, actor: User) -> ApprovalDelegation:
    # Read before the delegation is reloaded: reloading refreshes the user objects it points at, the actor included.
    can_manage = _can_manage(actor)
    delegation = await _get_delegation(db, delegation_id)
    involved = actor.id in (delegation.delegator_id, delegation.delegate_id)
    if not involved and not can_manage:
        # Not visible to this person, so it is reported like a record that does not exist.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delegation not found")
    if delegation.delegate_id == actor.id and not can_manage and delegation.delegator_id != actor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only the person who delegated can end a delegation"
        )
    if delegation.revoked_at is None:
        delegation.revoked_at = datetime.now(UTC)
        await record_audit_event(
            db,
            user_id=actor.id,
            action="approval_delegation_revoked",
            entity_type="user",
            entity_id=delegation.delegator_id,
            extra_data={"delegate_id": delegation.delegate_id},
        )
        await db.commit()
    return await _get_delegation(db, delegation_id)
