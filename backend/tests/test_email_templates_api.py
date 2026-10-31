from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from tests.fixture_types import AuthHeaders

BASE = "/api/v1/email-templates"


async def test_lists_every_template_with_its_variables(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    admin = await auth_headers("admin")
    response = await client.get(BASE, headers=admin)
    assert response.status_code == 200
    by_key = {t["key"]: t for t in response.json()}
    assert set(by_key) == {"invitation", "password_reset", "approval_needed", "po_to_supplier", "invoice_exception"}
    assert by_key["password_reset"]["variables"] == ["full_name", "link", "expires_in"]
    assert by_key["password_reset"]["is_customised"] is False


async def test_saving_customises_and_is_audited(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession
) -> None:
    admin = await auth_headers("admin")
    saved = await client.put(
        f"{BASE}/password_reset", headers=admin, json={"subject": "Reset {{ full_name }}", "body": "Go {{ link }}"}
    )
    assert saved.status_code == 200
    assert saved.json()["is_customised"] is True
    listed = {t["key"]: t for t in (await client.get(BASE, headers=admin)).json()}
    assert listed["password_reset"]["subject"] == "Reset {{ full_name }}"
    actions = (await db_session.execute(select(AuditLog.action))).scalars().all()
    assert "email_template_saved" in actions


async def test_unknown_variables_and_bad_syntax_are_rejected(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    admin = await auth_headers("admin")
    unknown = await client.put(f"{BASE}/password_reset", headers=admin, json={"subject": "Hi", "body": "{{ secret }}"})
    assert unknown.status_code == 422
    assert "secret" in unknown.json()["detail"]
    broken = await client.put(f"{BASE}/password_reset", headers=admin, json={"subject": "Hi", "body": "{% if %}"})
    assert broken.status_code == 422


async def test_unknown_template_key_is_404(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    admin = await auth_headers("admin")
    assert (await client.put(f"{BASE}/nope", headers=admin, json={"subject": "a", "body": "b"})).status_code == 404
    assert (await client.delete(f"{BASE}/nope", headers=admin)).status_code == 404


async def test_reset_restores_the_default(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    admin = await auth_headers("admin")
    await client.put(f"{BASE}/invitation", headers=admin, json={"subject": "Custom", "body": "Custom body"})
    reset = await client.delete(f"{BASE}/invitation", headers=admin)
    assert reset.status_code == 200
    assert reset.json()["is_customised"] is False
    assert reset.json()["subject"] == reset.json()["default_subject"]


async def test_only_settings_managers_can_use_it(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    viewer = await auth_headers("viewer")
    assert (await client.get(BASE, headers=viewer)).status_code == 403
    assert (
        await client.put(f"{BASE}/invitation", headers=viewer, json={"subject": "a", "body": "b"})
    ).status_code == 403
    assert (await client.get(BASE)).status_code == 401
