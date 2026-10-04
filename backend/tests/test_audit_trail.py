from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def _audit_events(db_session: AsyncSession, action: str, entity_id: int) -> list[AuditLog]:
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == action, AuditLog.entity_id == entity_id).order_by(AuditLog.id)
    )
    return list(result.scalars().all())


async def test_creating_a_category_records_an_audit_event(
    client: AsyncClient, auth_headers, db_session: AsyncSession
):
    headers = await auth_headers("admin")
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()

    response = await client.post("/api/v1/categories", json={"name": "Fasteners"}, headers=headers)

    assert response.status_code == 201
    category_id = response.json()["id"]
    events = await _audit_events(db_session, "category_created", category_id)
    assert len(events) == 1
    assert events[0].entity_type == "category"
    assert events[0].user_id == me["id"]
