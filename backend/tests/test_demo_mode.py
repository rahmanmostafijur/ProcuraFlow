"""Demo mode: the public sign-in endpoints, the one list of blocked actions, and email that is only logged."""

from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.demo_guard import DEMO_RULES, find_blocking_rule, seeding_allowed
from app.core.security import hash_password
from app.demo.accounts import ACCOUNTS_BY_KEY, DEMO_ACCOUNTS, demo_password
from app.models.email import OUTBOX_LOGGED, OUTBOX_QUEUED, OUTBOX_SENT, EmailOutbox
from app.models.role import Role
from app.models.supplier import Supplier
from app.models.user import User
from app.services import email_service
from tests.fixture_types import AuthHeaders, MakeUser

API = "/api/v1"
ACCOUNTS_URL = f"{API}/auth/demo-accounts"
LOGIN_URL = f"{API}/auth/demo-login"
BLOCKED = "This action is turned off in the demo"
STRONG_SECRET = "k3Vq9xLr0TzP7mWb2NcY8sHd5FgJ1aUe6RoXiQ4vEyZt"


@pytest.fixture
def demo_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "demo_mode", True)


async def _demo_user(db: AsyncSession, roles: dict[str, Role], key: str, supplier: Supplier | None = None) -> User:
    account = ACCOUNTS_BY_KEY[key]
    user = User(
        email=account.email,
        full_name=account.full_name,
        hashed_password=hash_password(demo_password(get_settings())),
        role_id=roles[account.role_name].id,
        supplier_id=supplier.id if supplier else None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# --- the demo endpoints exist only in demo mode ------------------------------------------------------------------


async def test_the_demo_accounts_endpoint_does_not_exist_outside_the_demo(client: AsyncClient) -> None:
    response = await client.get(ACCOUNTS_URL)

    assert response.status_code == 404


async def test_the_demo_login_endpoint_does_not_exist_outside_the_demo(
    client: AsyncClient, db_session: AsyncSession, roles: dict[str, Role]
) -> None:
    await _demo_user(db_session, roles, "admin")

    response = await client.post(LOGIN_URL, json={"role": "admin"})

    assert response.status_code == 404


@pytest.mark.usefixtures("demo_on")
async def test_the_demo_accounts_are_listed_without_signing_in(client: AsyncClient) -> None:
    response = await client.get(ACCOUNTS_URL)

    body = response.json()
    assert response.status_code == 200
    assert [entry["role"] for entry in body] == [account.key for account in DEMO_ACCOUNTS]
    assert {entry["role_name"] for entry in body} >= {"admin", "finance", "employee", "viewer", "supplier"}
    assert [entry["role"] for entry in body if entry["is_portal"]] == ["supplier", "supplier_eu"]
    assert all(entry["email"].endswith("@demo.example.com") for entry in body)
    assert all("password" not in entry for entry in body)


@pytest.mark.usefixtures("demo_on")
async def test_demo_login_signs_in_through_the_normal_session_path(
    client: AsyncClient, db_session: AsyncSession, roles: dict[str, Role]
) -> None:
    await _demo_user(db_session, roles, "finance")

    response = await client.post(LOGIN_URL, json={"role": "finance"})

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert "refresh_token" in response.headers["set-cookie"]
    me = await client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"})
    assert (me.json()["email"], me.json()["role"]["name"]) == ("finance@demo.example.com", "finance")


@pytest.mark.usefixtures("demo_on")
async def test_demo_login_as_a_supplier_reaches_the_portal_only(
    client: AsyncClient, db_session: AsyncSession, roles: dict[str, Role], supplier: Supplier
) -> None:
    await _demo_user(db_session, roles, "supplier", supplier)

    token = (await client.post(LOGIN_URL, json={"role": "supplier"})).json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}
    assert (await client.get(f"{API}/portal/orders", headers=headers)).status_code == 200
    assert (await client.get(f"{API}/suppliers", headers=headers)).status_code == 403


@pytest.mark.usefixtures("demo_on")
async def test_demo_login_rejects_an_unknown_role(client: AsyncClient) -> None:
    response = await client.post(LOGIN_URL, json={"role": "root"})

    assert response.status_code == 404


@pytest.mark.usefixtures("demo_on")
async def test_demo_login_explains_when_the_demo_data_is_missing(client: AsyncClient) -> None:
    response = await client.post(LOGIN_URL, json={"role": "admin"})

    assert response.status_code == 409
    assert "demo_reset" in response.json()["detail"]


@pytest.mark.usefixtures("demo_on")
async def test_demo_login_refuses_a_deactivated_account(
    client: AsyncClient, db_session: AsyncSession, roles: dict[str, Role]
) -> None:
    user = await _demo_user(db_session, roles, "viewer")
    user.is_active = False
    await db_session.commit()

    assert (await client.post(LOGIN_URL, json={"role": "viewer"})).status_code == 409


# --- demo passwords only work in demo mode ------------------------------------------------------------------------


async def test_demo_accounts_cannot_sign_in_or_use_old_tokens_once_the_demo_is_off(
    client: AsyncClient, db_session: AsyncSession, roles: dict[str, Role], monkeypatch: pytest.MonkeyPatch
) -> None:
    await _demo_user(db_session, roles, "admin")
    settings = get_settings()
    credentials = {"email": ACCOUNTS_BY_KEY["admin"].email, "password": demo_password(settings)}
    monkeypatch.setattr(settings, "demo_mode", True)
    signed_in = await client.post(f"{API}/auth/login", json=credentials)
    headers = {"Authorization": f"Bearer {signed_in.json()['access_token']}"}
    monkeypatch.setattr(settings, "demo_mode", False)

    after_login = await client.post(f"{API}/auth/login", json=credentials)
    after_token = await client.get(f"{API}/auth/me", headers=headers)

    assert signed_in.status_code == 200
    assert (after_login.status_code, after_token.status_code) == (401, 401)


async def test_a_demo_refresh_cookie_stops_working_once_the_demo_is_off(
    client: AsyncClient, db_session: AsyncSession, roles: dict[str, Role], monkeypatch: pytest.MonkeyPatch
) -> None:
    await _demo_user(db_session, roles, "admin")
    settings = get_settings()
    monkeypatch.setattr(settings, "demo_mode", True)
    assert (await client.post(LOGIN_URL, json={"role": "admin"})).status_code == 200
    assert (await client.post(f"{API}/auth/refresh")).status_code == 200
    monkeypatch.setattr(settings, "demo_mode", False)

    after = await client.post(f"{API}/auth/refresh")

    assert after.status_code == 401


@pytest.mark.usefixtures("demo_on")
async def test_a_demo_admin_cannot_create_an_account_with_a_password_of_their_choosing(
    client: AsyncClient, db_session: AsyncSession, roles: dict[str, Role]
) -> None:
    await _demo_user(db_session, roles, "admin")
    token = (await client.post(LOGIN_URL, json={"role": "admin"})).json()["access_token"]
    body = {
        "email": "new.admin@example.com",
        "full_name": "New Admin",
        "role_id": roles["admin"].id,
        "password": "A-long-password-1",
    }

    response = await client.post(f"{API}/users", json=body, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    assert BLOCKED in response.json()["detail"]


def test_the_demo_password_comes_from_configuration() -> None:
    base: dict[str, Any] = {"_env_file": None, "environment": "test", "jwt_secret_key": STRONG_SECRET}
    derived = demo_password(Settings(**base))
    other_secret = demo_password(Settings(**{**base, "jwt_secret_key": STRONG_SECRET[::-1]}))
    configured = demo_password(Settings(**base, demo_password="a-configured-demo-password"))

    assert derived == demo_password(Settings(**base))
    assert len(derived) == 20
    assert derived != other_secret
    assert configured == "a-configured-demo-password"


# --- destructive actions are blocked with a clear 403 --------------------------------------------------------------


@pytest.mark.usefixtures("demo_on")
@pytest.mark.parametrize(
    "body",
    [{"is_active": False}, {"role_id": 1}, {"password": "A-new-password-1"}],
    ids=["deactivate", "change-role", "change-password"],
)
async def test_users_cannot_be_deactivated_re_roled_or_given_a_new_password(
    client: AsyncClient, auth_headers: AuthHeaders, make_user: MakeUser, body: dict[str, Any]
) -> None:
    admin = await auth_headers("admin")
    target = await make_user("target@example.com", "viewer")

    response = await client.patch(f"{API}/users/{target.id}", json=body, headers=admin)

    assert response.status_code == 403
    assert response.json()["detail"].startswith(BLOCKED)


@pytest.mark.usefixtures("demo_on")
async def test_ordinary_user_edits_stay_possible_in_the_demo(
    client: AsyncClient, auth_headers: AuthHeaders, make_user: MakeUser
) -> None:
    admin = await auth_headers("admin")
    target = await make_user("target@example.com", "viewer")

    response = await client.patch(f"{API}/users/{target.id}", json={"full_name": "Renamed Person"}, headers=admin)

    assert response.status_code == 200


@pytest.mark.usefixtures("demo_on")
async def test_a_signed_in_user_cannot_change_their_password_in_the_demo(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    headers = await auth_headers("viewer")

    response = await client.post(
        f"{API}/auth/change-password",
        json={"current_password": "TestPass123!", "new_password": "Another-pass-456"},
        headers=headers,
    )

    assert response.status_code == 403
    assert "Demo passwords cannot be changed" in response.json()["detail"]


@pytest.mark.usefixtures("demo_on")
async def test_password_reset_confirmation_is_blocked_in_the_demo(client: AsyncClient) -> None:
    response = await client.post(
        f"{API}/auth/password-reset/confirm", json={"token": "x" * 30, "password": "Another-pass-456"}
    )

    assert response.status_code == 403


@pytest.mark.usefixtures("demo_on")
async def test_anonymising_people_is_blocked_in_the_demo(
    client: AsyncClient, auth_headers: AuthHeaders, make_user: MakeUser, supplier: Supplier
) -> None:
    admin = await auth_headers("admin")
    target = await make_user("target@example.com", "viewer")

    user_response = await client.post(f"{API}/gdpr/users/{target.id}/anonymise", headers=admin)
    contact_response = await client.post(f"{API}/gdpr/suppliers/{supplier.id}/contact/anonymise", headers=admin)

    assert (user_response.status_code, contact_response.status_code) == (403, 403)


@pytest.mark.usefixtures("demo_on")
async def test_data_exports_stay_available_in_the_demo(
    client: AsyncClient, auth_headers: AuthHeaders, make_user: MakeUser
) -> None:
    admin = await auth_headers("admin")
    target = await make_user("target@example.com", "viewer")

    response = await client.get(f"{API}/gdpr/users/{target.id}/export", headers=admin)

    assert response.status_code == 200


@pytest.mark.usefixtures("demo_on")
@pytest.mark.parametrize(
    "body",
    [{"base_currency_code": "GBP"}, {"timezone": "UTC"}, {"payer_iban": None}, {"invoice_matching": "two_way"}],
)
async def test_company_settings_the_demo_depends_on_cannot_change(
    client: AsyncClient, auth_headers: AuthHeaders, body: dict[str, Any]
) -> None:
    admin = await auth_headers("admin")

    response = await client.patch(f"{API}/company-settings", json=body, headers=admin)

    assert response.status_code == 403
    assert response.json()["detail"].startswith(BLOCKED)


@pytest.mark.usefixtures("demo_on")
async def test_branding_can_still_be_edited_in_the_demo(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    admin = await auth_headers("admin")

    response = await client.patch(f"{API}/company-settings", json={"company_name": "Renamed Co"}, headers=admin)

    assert response.status_code == 200


@pytest.mark.usefixtures("demo_on")
async def test_exchange_rates_cannot_be_deleted_in_the_demo(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    finance = await auth_headers("finance")

    response = await client.delete(f"{API}/exchange-rates/1", headers=finance)

    assert response.status_code == 403


async def test_nothing_is_blocked_outside_the_demo(
    client: AsyncClient, auth_headers: AuthHeaders, make_user: MakeUser
) -> None:
    admin = await auth_headers("admin")
    target = await make_user("target@example.com", "viewer")

    deactivated = await client.patch(f"{API}/users/{target.id}", json={"is_active": False}, headers=admin)
    settings = await client.patch(f"{API}/company-settings", json={"timezone": "Europe/Berlin"}, headers=admin)

    assert (deactivated.status_code, settings.status_code) == (200, 200)


@pytest.mark.usefixtures("demo_on")
async def test_the_seed_may_do_what_a_visitor_may_not(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    admin = await auth_headers("admin")

    with seeding_allowed():
        allowed = await client.patch(f"{API}/company-settings", json={"timezone": "Europe/Berlin"}, headers=admin)
    refused = await client.patch(f"{API}/company-settings", json={"timezone": "UTC"}, headers=admin)

    assert (allowed.status_code, refused.status_code) == (200, 403)


@pytest.mark.parametrize(
    ("method", "path", "body", "blocked"),
    [
        ("POST", "/api/v1/users", {"email": "x@example.com", "role_id": 1, "password": "A-long-password-1"}, True),
        ("POST", "/api/v1/users/invite", {"email": "x@example.com", "role_id": 2}, False),
        ("DELETE", "/api/v1/users/5", None, True),
        ("PATCH", "/api/v1/users/5", {"is_active": False}, True),
        ("PATCH", "/api/v1/users/5", {"is_active": True}, False),
        ("PATCH", "/api/v1/users/5", None, False),
        ("PATCH", "/api/v1/users/5/", {"role_id": 2}, True),
        ("POST", "/api/v1/auth/change-password", None, True),
        ("POST", "/api/v1/gdpr/users/5/anonymise", None, True),
        ("POST", "/api/v1/gdpr/users/5/export", None, False),
        ("PATCH", "/api/v1/company-settings", {"company_name": "X"}, False),
        ("PATCH", "/api/v1/company-settings", {"fiscal_year_start_month": 4}, True),
        ("DELETE", "/api/v1/exchange-rates/9", None, True),
        ("GET", "/api/v1/exchange-rates", None, False),
    ],
)
def test_the_rule_list_matches_what_it_documents(
    method: str, path: str, body: dict[str, Any] | None, blocked: bool
) -> None:
    assert (find_blocking_rule(method, path, body) is not None) is blocked


def test_every_rule_has_a_reason_a_visitor_can_read() -> None:
    assert all(rule.reason and rule.reason[0].isupper() for rule in DEMO_RULES)


# --- email is only logged ------------------------------------------------------------------------------------------


def _message() -> EmailOutbox:
    return EmailOutbox(
        to_address="someone@example.com",
        subject="Hello",
        body="Body",
        template_key="po_to_supplier",
        status=OUTBOX_QUEUED,
        attempts=0,
    )


def _smtp_settings(**overrides: Any) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        jwt_secret_key=STRONG_SECRET,
        smtp_host="smtp.invalid",
        **overrides,
    )


def test_demo_mode_logs_email_and_never_sends_it_even_with_smtp_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_: Any, **__: Any) -> None:
        raise AssertionError("the demo must not open an SMTP connection")

    monkeypatch.setattr(email_service, "_send_smtp", refuse)
    row = _message()

    email_service.deliver(_smtp_settings(demo_mode=True), row)

    assert row.status == OUTBOX_LOGGED
    assert row.attempts == 1
    assert isinstance(row.sent_at, datetime)
    assert row.sent_at.tzinfo is UTC


def test_outside_the_demo_a_configured_smtp_host_is_still_used(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[str] = []
    monkeypatch.setattr(email_service, "_send_smtp", lambda settings, host, message: sent.append(host))
    row = _message()

    email_service.deliver(_smtp_settings(), row)

    assert sent == ["smtp.invalid"]
    assert row.status == OUTBOX_SENT
