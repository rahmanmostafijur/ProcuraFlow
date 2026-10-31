from datetime import UTC, datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import ApprovalStep
from app.models.enums import ApprovalDocumentType
from app.models.notification import Notification
from app.models.role import Role
from app.models.user import User
from app.services.notification_service import notify_overdue_approvals
from tests.fixture_types import AuthHeaders, MakeUser

BASE = "/api/v1/notifications"


async def _user_id(db: AsyncSession, email: str) -> int:
    return (await db.execute(select(User.id).where(User.email == email))).scalar_one()


async def test_users_see_only_their_own_notifications(
    client: AsyncClient, auth_headers: AuthHeaders, make_user: MakeUser, db_session: AsyncSession
) -> None:
    mine = await auth_headers("purchasing")
    await make_user("other@example.com", "purchasing")
    db_session.add_all(
        [
            Notification(user_id=await _user_id(db_session, "purchasing@example.com"), message="for me"),
            Notification(user_id=await _user_id(db_session, "other@example.com"), message="for someone else"),
        ]
    )
    await db_session.commit()

    listed = (await client.get(BASE, headers=mine)).json()
    assert [n["message"] for n in listed] == ["for me"]
    assert (await client.get(f"{BASE}/unread-count", headers=mine)).json() == {"unread": 1}


async def test_marking_read_updates_the_count_and_is_scoped_to_the_owner(
    client: AsyncClient, auth_headers: AuthHeaders, make_user: MakeUser, db_session: AsyncSession
) -> None:
    mine = await auth_headers("purchasing")
    other = await make_user("other@example.com", "purchasing")
    theirs = Notification(user_id=other.id, message="theirs")
    own = Notification(user_id=await _user_id(db_session, "purchasing@example.com"), message="own")
    db_session.add_all([theirs, own])
    await db_session.commit()

    assert (await client.post(f"{BASE}/{theirs.id}/read", headers=mine)).status_code == 404
    assert (await client.post(f"{BASE}/{own.id}/read", headers=mine)).status_code == 204
    assert (await client.get(f"{BASE}/unread-count", headers=mine)).json() == {"unread": 0}
    await db_session.refresh(theirs)
    assert theirs.is_read is False


async def test_read_all_only_touches_the_callers_notifications(
    client: AsyncClient, auth_headers: AuthHeaders, make_user: MakeUser, db_session: AsyncSession
) -> None:
    mine = await auth_headers("purchasing")
    other = await make_user("other@example.com", "purchasing")
    me = await _user_id(db_session, "purchasing@example.com")
    db_session.add_all([Notification(user_id=me, message="a"), Notification(user_id=other.id, message="b")])
    await db_session.commit()

    assert (await client.post(f"{BASE}/read-all", headers=mine)).json() == {"unread": 0}
    remaining = (await db_session.execute(select(Notification).where(Notification.is_read.is_(False)))).scalars().all()
    assert [n.user_id for n in remaining] == [other.id]


async def test_notifications_need_sign_in(client: AsyncClient) -> None:
    assert (await client.get(BASE)).status_code == 401


async def _pending_step(db: AsyncSession, role: Role, age: timedelta) -> None:
    db.add(
        ApprovalStep(
            document_type=ApprovalDocumentType.PURCHASE_ORDER,
            document_id=7,
            round=1,
            step_order=1,
            approver_role_id=role.id,
            amount_base=Decimal(100),
            created_at=datetime.now(UTC) - age,
        )
    )
    await db.commit()


async def test_overdue_approvals_notify_the_role_once_per_reminder_window(
    make_user: MakeUser, roles: dict[str, Role], db_session: AsyncSession
) -> None:
    approver = await make_user("approver@example.com", "admin")
    await make_user("bystander@example.com", "viewer")
    await _pending_step(db_session, roles["admin"], timedelta(days=4))

    assert await notify_overdue_approvals(db_session) == 1
    assert await notify_overdue_approvals(db_session) == 0
    rows = (await db_session.execute(select(Notification))).scalars().all()
    assert [(n.user_id, "purchase_order #7" in n.message) for n in rows] == [(approver.id, True)]

    later = datetime.now(UTC) + timedelta(days=8)
    assert await notify_overdue_approvals(db_session, later) == 1


async def test_a_recent_pending_step_is_not_overdue(
    make_user: MakeUser, roles: dict[str, Role], db_session: AsyncSession
) -> None:
    await make_user("approver@example.com", "admin")
    await _pending_step(db_session, roles["admin"], timedelta(days=1))
    assert await notify_overdue_approvals(db_session) == 0
