from collections.abc import Callable

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

RECENT_ACTIVITY_URL = "/api/v1/dashboard/recent-activity"
AUDIT_READ_DENIED = "You do not have the 'audit:read' permission"


@pytest.mark.parametrize("role_name", ["viewer", "purchasing_officer", "warehouse_manager"])
async def test_recent_activity_requires_audit_read(
    client: AsyncClient, db_session: AsyncSession, auth_headers: Callable, role_name: str
) -> None:
    headers = await auth_headers(role_name)
    db_session.add(AuditLog(action="supplier_created", entity_type="supplier", entity_id=1))
    await db_session.commit()

    response = await client.get(RECENT_ACTIVITY_URL, headers=headers)

    assert response.status_code == 403
    assert response.json() == {"detail": AUDIT_READ_DENIED}


@pytest.mark.parametrize("role_name", ["procurement_manager", "admin"])
async def test_recent_activity_is_returned_to_audit_readers(
    client: AsyncClient, db_session: AsyncSession, auth_headers: Callable, role_name: str
) -> None:
    headers = await auth_headers(role_name)
    db_session.add(AuditLog(action="supplier_created", entity_type="supplier", entity_id=1))
    await db_session.commit()

    response = await client.get(RECENT_ACTIVITY_URL, headers=headers)

    assert response.status_code == 200
    assert "supplier_created" in [item["action"] for item in response.json()]


@pytest.mark.parametrize("limit", [0, 51])
async def test_recent_activity_rejects_out_of_range_limit(
    client: AsyncClient, auth_headers: Callable, limit: int
) -> None:
    headers = await auth_headers("procurement_manager")

    response = await client.get(RECENT_ACTIVITY_URL, headers=headers, params={"limit": limit})

    assert response.status_code == 422
    [error] = response.json()["detail"]
    assert error["loc"] == ["query", "limit"]


async def test_recent_activity_accepts_the_maximum_limit(
    client: AsyncClient, db_session: AsyncSession, auth_headers: Callable
) -> None:
    headers = await auth_headers("procurement_manager")
    db_session.add_all(
        AuditLog(action="supplier_created", entity_type="supplier", entity_id=n) for n in range(51)
    )
    await db_session.commit()

    response = await client.get(RECENT_ACTIVITY_URL, headers=headers, params={"limit": 50})

    assert response.status_code == 200
    assert len(response.json()) == 50


MONTHLY_TRENDS_URL = "/api/v1/dashboard/monthly-trends"


@pytest.mark.parametrize("months", [0, 25])
async def test_monthly_trends_rejects_out_of_range_window(
    client: AsyncClient, auth_headers: Callable, months: int
) -> None:
    headers = await auth_headers("viewer")

    response = await client.get(MONTHLY_TRENDS_URL, headers=headers, params={"months": months})

    assert response.status_code == 422
    [error] = response.json()["detail"]
    assert error["loc"] == ["query", "months"]


@pytest.mark.parametrize("params", [{}, {"months": 1}, {"months": 24}])
async def test_monthly_trends_accepts_the_default_and_bounds(
    client: AsyncClient, auth_headers: Callable, params: dict[str, int]
) -> None:
    headers = await auth_headers("viewer")

    response = await client.get(MONTHLY_TRENDS_URL, headers=headers, params=params)

    assert response.status_code == 200
    assert response.json() == []
