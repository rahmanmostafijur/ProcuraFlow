from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_today
from app.models.audit import AuditLog
from tests.fixture_types import AuthHeaders

CURRENCIES_URL = "/api/v1/currencies"
RATES_URL = "/api/v1/exchange-rates"


async def test_currencies_require_sign_in(client: AsyncClient) -> None:
    assert (await client.get(CURRENCIES_URL)).status_code == 401
    assert (await client.get(RATES_URL)).status_code == 401


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("POST", CURRENCIES_URL),
        ("PATCH", f"{CURRENCIES_URL}/EUR"),
        ("POST", RATES_URL),
        ("DELETE", f"{RATES_URL}/1"),
        ("POST", "/api/v1/tax-rates"),
        ("PATCH", "/api/v1/tax-rates/1"),
    ],
)
async def test_reference_data_cannot_be_written_without_signing_in(client: AsyncClient, method: str, url: str) -> None:
    response = await client.request(method, url, json={})

    assert response.status_code == 401


async def test_any_signed_in_user_lists_currencies(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("viewer")

    response = await client.get(CURRENCIES_URL, headers=headers)

    assert response.status_code == 200
    by_code = {row["code"]: row for row in response.json()}
    assert by_code["USD"] == {"code": "USD", "name": "US Dollar", "symbol": "$", "minor_units": 2, "is_active": True}
    assert by_code["JPY"]["minor_units"] == 0
    assert by_code["BHD"]["minor_units"] == 3


async def test_active_only_filter_hides_switched_off_currencies(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("viewer")

    response = await client.get(CURRENCIES_URL, params={"active_only": True}, headers=headers)

    codes = {row["code"] for row in response.json()}
    assert {"USD", "EUR", "GBP"} <= codes
    assert "JPY" not in codes


async def test_finance_adds_a_currency_and_it_is_audited(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession
) -> None:
    headers = await auth_headers("finance")

    response = await client.post(
        CURRENCIES_URL, json={"code": "xts", "name": "Test Scrip", "symbol": "T$", "minor_units": 2}, headers=headers
    )

    assert response.status_code == 201
    assert response.json()["code"] == "XTS"
    assert response.json()["is_active"] is True
    audit = await db_session.scalar(select(AuditLog).where(AuditLog.action == "currency_created"))
    assert audit is not None
    assert audit.extra_data == {"code": "XTS"}


async def test_duplicate_currency_code_conflicts(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("finance")

    response = await client.post(
        CURRENCIES_URL, json={"code": "EUR", "name": "Again", "symbol": "E", "minor_units": 2}, headers=headers
    )

    assert response.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"code": "EU", "name": "Short", "symbol": "E", "minor_units": 2},
        {"code": "EURO", "name": "Long", "symbol": "E", "minor_units": 2},
        {"code": "E1R", "name": "Digit", "symbol": "E", "minor_units": 2},
        {"code": "XTS", "name": "", "symbol": "T", "minor_units": 2},
        {"code": "XTS", "name": "Test", "symbol": "", "minor_units": 2},
        {"code": "XTS", "name": "Test", "symbol": "T", "minor_units": 5},
        {"code": "XTS", "name": "Test", "symbol": "T", "minor_units": -1},
    ],
)
async def test_invalid_currency_is_rejected(
    client: AsyncClient, auth_headers: AuthHeaders, payload: dict[str, Any]
) -> None:
    headers = await auth_headers("finance")

    response = await client.post(CURRENCIES_URL, json=payload, headers=headers)

    assert response.status_code == 422


@pytest.mark.parametrize("role", ["viewer", "procurement_manager", "purchasing_officer", "warehouse_manager"])
async def test_only_finance_can_change_currencies(client: AsyncClient, auth_headers: AuthHeaders, role: str) -> None:
    headers = await auth_headers(role)

    create = await client.post(
        CURRENCIES_URL, json={"code": "XTS", "name": "Test", "symbol": "T", "minor_units": 2}, headers=headers
    )
    update = await client.patch(f"{CURRENCIES_URL}/EUR", json={"is_active": False}, headers=headers)

    assert create.status_code == 403
    assert update.status_code == 403


async def test_a_currency_can_be_switched_on_and_off(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("finance")

    on = await client.patch(f"{CURRENCIES_URL}/czk", json={"is_active": True}, headers=headers)
    off = await client.patch(f"{CURRENCIES_URL}/CZK", json={"is_active": False}, headers=headers)

    assert on.status_code == 200
    assert on.json()["is_active"] is True
    assert off.json()["is_active"] is False


async def test_minor_units_cannot_be_changed_after_the_fact(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("finance")

    response = await client.patch(f"{CURRENCIES_URL}/USD", json={"minor_units": 0}, headers=headers)

    # The field is not part of the update schema, so it is ignored and the rounding rule stays as it was.
    assert response.status_code == 200
    assert response.json()["minor_units"] == 2


async def test_the_base_currency_cannot_be_switched_off(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("finance")

    response = await client.patch(f"{CURRENCIES_URL}/USD", json={"is_active": False}, headers=headers)

    assert response.status_code == 409


async def test_updating_an_unknown_currency_is_404(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("finance")

    response = await client.patch(f"{CURRENCIES_URL}/ZZZ", json={"name": "Nope"}, headers=headers)

    assert response.status_code == 404


async def _add_rate(client: AsyncClient, headers: dict[str, str], **overrides: Any) -> Any:
    payload = {"currency_code": "EUR", "rate": "1.08", "effective_date": utc_today().isoformat(), **overrides}
    return await client.post(RATES_URL, json=payload, headers=headers)


async def test_finance_enters_a_rate_and_anyone_can_read_it(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    finance = await auth_headers("finance")
    viewer = await auth_headers("viewer")

    created = await _add_rate(client, finance, rate="1.08345678")
    listed = await client.get(RATES_URL, headers=viewer)

    assert created.status_code == 201
    assert created.json()["base_currency_code"] == "USD"
    assert created.json()["rate"] == "1.08345678"
    assert [row["currency_code"] for row in listed.json()["items"]] == ["EUR"]


async def test_rates_list_newest_first_and_filter_by_currency(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("finance")
    today = utc_today()
    await _add_rate(client, headers, rate="1.05", effective_date=(today - timedelta(days=10)).isoformat())
    await _add_rate(client, headers, rate="1.10", effective_date=today.isoformat())
    await _add_rate(client, headers, currency_code="GBP", rate="1.30")

    eur = await client.get(RATES_URL, params={"currency_code": "EUR"}, headers=headers)

    assert [row["rate"] for row in eur.json()["items"]] == ["1.10000000", "1.05000000"]
    assert eur.json()["total"] == 2


async def test_a_second_rate_for_the_same_day_conflicts(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("finance")
    await _add_rate(client, headers)

    response = await _add_rate(client, headers, rate="1.09")

    assert response.status_code == 409


async def test_a_rate_for_the_base_currency_is_refused(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("finance")

    response = await _add_rate(client, headers, currency_code="USD", rate="1")

    assert response.status_code == 422


async def test_a_rate_for_an_inactive_or_unknown_currency_is_refused(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    headers = await auth_headers("finance")

    inactive = await _add_rate(client, headers, currency_code="JPY", rate="0.0067")
    unknown = await _add_rate(client, headers, currency_code="ZZZ", rate="2")

    assert inactive.status_code == 400
    assert unknown.status_code == 400


@pytest.mark.parametrize("rate", ["0", "-1", "1.123456789", "1000000000", "abc"])
async def test_invalid_rates_are_rejected(client: AsyncClient, auth_headers: AuthHeaders, rate: str) -> None:
    headers = await auth_headers("finance")

    response = await _add_rate(client, headers, rate=rate)

    assert response.status_code == 422


async def test_only_finance_can_enter_or_remove_rates(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    finance = await auth_headers("finance")
    manager = await auth_headers("procurement_manager")
    rate_id = (await _add_rate(client, finance)).json()["id"]

    add = await _add_rate(client, manager, currency_code="GBP")
    remove = await client.delete(f"{RATES_URL}/{rate_id}", headers=manager)

    assert add.status_code == 403
    assert remove.status_code == 403


async def test_deleting_a_rate_removes_it_and_is_audited(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession
) -> None:
    headers = await auth_headers("finance")
    rate_id = (await _add_rate(client, headers)).json()["id"]

    removed = await client.delete(f"{RATES_URL}/{rate_id}", headers=headers)
    again = await client.delete(f"{RATES_URL}/{rate_id}", headers=headers)

    assert removed.status_code == 204
    assert again.status_code == 404
    assert (await client.get(RATES_URL, headers=headers)).json()["total"] == 0
    audit = await db_session.scalar(select(AuditLog).where(AuditLog.action == "exchange_rate_deleted"))
    assert audit is not None
