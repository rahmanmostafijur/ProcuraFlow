from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import ApprovalStep
from app.models.enums import ApprovalStepStatus
from app.models.notification import Notification
from app.models.permission import Permission, role_permissions
from app.models.user import User

OVERDUE_AFTER = timedelta(days=3)
REMINDER_EVERY = timedelta(days=7)
MAX_MESSAGE_LENGTH = 500
PAGE_LIMIT = 100


def _now() -> datetime:
    return datetime.now(UTC)


async def list_for_user(db: AsyncSession, user_id: int, *, unread_only: bool = False) -> list[Notification]:
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    result = await db.execute(stmt.order_by(Notification.id.desc()).limit(PAGE_LIMIT))
    return list(result.scalars().all())


async def unread_count(db: AsyncSession, user_id: int) -> int:
    count = await db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
    )
    return count or 0


async def mark_read(db: AsyncSession, user_id: int, notification_id: int) -> bool:
    """Mark one of the user's own notifications read. False when it is not theirs or does not exist."""
    result = await db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user_id)
        .values(is_read=True)
    )
    return result.rowcount > 0


async def mark_all_read(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    return result.rowcount


async def _approvers(db: AsyncSession, step: ApprovalStep) -> list[int]:
    """Active users who could decide this step: holders of its role, or of the permission it requires."""
    stmt = select(User.id).where(User.is_active.is_(True))
    if step.approver_role_id is not None:
        stmt = stmt.where(User.role_id == step.approver_role_id)
    else:
        stmt = stmt.where(
            User.role_id.in_(
                select(role_permissions.c.role_id)
                .join(Permission, Permission.id == role_permissions.c.permission_id)
                .where(Permission.code == step.required_permission)
            )
        )
    return list((await db.execute(stmt)).scalars().all())


async def _already_reminded(db: AsyncSession, user_id: int, prefix: str, now: datetime) -> bool:
    found = await db.scalar(
        select(Notification.id)
        .where(
            Notification.user_id == user_id,
            Notification.message.startswith(prefix),
            Notification.created_at > now - REMINDER_EVERY,
        )
        .limit(1)
    )
    return found is not None


async def notify_overdue_approvals(db: AsyncSession, now: datetime | None = None) -> int:
    """Remind approvers of steps pending for OVERDUE_AFTER or longer, at most once per REMINDER_EVERY each."""
    now = now or _now()
    steps = (
        (
            await db.execute(
                select(ApprovalStep).where(
                    ApprovalStep.status == ApprovalStepStatus.PENDING,
                    ApprovalStep.created_at <= now - OVERDUE_AFTER,
                    or_(ApprovalStep.approver_role_id.is_not(None), ApprovalStep.required_permission.is_not(None)),
                )
            )
        )
        .scalars()
        .all()
    )
    created = 0
    for step in steps:
        days = (now - step.created_at).days
        prefix = f"Approval overdue: {step.document_type.value} #{step.document_id}"
        for user_id in await _approvers(db, step):
            if await _already_reminded(db, user_id, prefix, now):
                continue
            message = f"{prefix} has been waiting {days} days"
            db.add(Notification(user_id=user_id, message=message[:MAX_MESSAGE_LENGTH]))
            created += 1
    await db.commit()
    return created
