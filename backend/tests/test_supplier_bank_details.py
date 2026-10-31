"""Supplier bank details: validated, changed only with a second person's approval, history kept."""

import json
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.bank_validation import is_valid_iban, is_valid_routing_number
from app.models.audit import AuditLog
from app.models.notification import Notification
from app.models.supplier import Supplier
from app.models.supplier_bank import SupplierBankDetails
from tests.fixture_types import AuthHeaders
from tests.flow_helpers import API

GERMAN_IBAN = "DE89370400440532013000"
FRENCH_IBAN = "FR1420041010050500013M02606"
VALID_ROUTING = "021000021"  # JPMorgan Chase, a published ABA number


def _url(supplier_id: int, suffix: str = "") -> str:
    return f"{API}/suppliers/{supplier_id}/bank-details{suffix}"


def _sepa_body(**overrides: Any) -> dict[str, Any]:
    return {
        "bank_account_name": "Test Supplier GmbH",
        "bank_country": "DE",
        "iban": GERMAN_IBAN,
        "bic": "COBADEFFXXX",
    } | overrides


async def _request(client: AsyncClient, headers: dict[str, str], supplier_id: int, body: dict[str, Any]) -> Response:
    return await client.post(_url(supplier_id, "/changes"), json=body, headers=headers)


async def _decide(
    client: AsyncClient, headers: dict[str, str], supplier_id: int, change_id: int, action: str = "approve"
) -> Response:
    return await client.post(_url(supplier_id, f"/changes/{change_id}/{action}"), json={}, headers=headers)


@pytest.fixture
async def finance(auth_headers: AuthHeaders) -> dict[str, str]:
    return await auth_headers("finance")


@pytest.fixture
async def finance2(auth_headers: AuthHeaders) -> dict[str, str]:
    return await auth_headers("finance", "finance2@example.com")


def test_iban_and_routing_checksums() -> None:
    assert is_valid_iban(GERMAN_IBAN)
    assert is_valid_iban(FRENCH_IBAN)
    assert not is_valid_iban("DE89370400440532013001")
    assert not is_valid_iban("DE00")
    assert is_valid_routing_number(VALID_ROUTING)
    assert not is_valid_routing_number("021000022")
    assert not is_valid_routing_number("12345")


async def test_a_change_needs_a_second_person_and_the_old_details_stay_in_the_history(
    client: AsyncClient, finance: dict[str, str], finance2: dict[str, str], supplier: Supplier
) -> None:
    first = (await _request(client, finance, supplier.id, _sepa_body())).json()
    approved_first = await _decide(client, finance2, supplier.id, first["id"])
    second = (await _request(client, finance, supplier.id, _sepa_body(iban=FRENCH_IBAN, bank_country="FR"))).json()
    approved_second = await _decide(client, finance2, supplier.id, second["id"])

    overview = (await client.get(_url(supplier.id), headers=finance)).json()

    assert (first["status"], approved_first.json()["status"]) == ("pending", "current")
    assert approved_second.status_code == 200
    assert overview["current"]["iban"] == FRENCH_IBAN
    assert overview["pending"] is None
    assert [(row["iban"], row["status"]) for row in overview["history"]] == [(GERMAN_IBAN, "superseded")]
    assert overview["history"][0]["superseded_at"] is not None
    assert overview["history"][0]["decided_by"]["full_name"] == "Finance User"


async def test_the_requester_cannot_approve_their_own_change(
    client: AsyncClient, finance: dict[str, str], finance2: dict[str, str], supplier: Supplier
) -> None:
    change = (await _request(client, finance, supplier.id, _sepa_body())).json()

    refused = await _decide(client, finance, supplier.id, change["id"])
    overview = (await client.get(_url(supplier.id), headers=finance)).json()

    assert refused.status_code == 403
    assert "second person" in refused.json()["detail"]
    assert overview["current"] is None
    assert overview["pending"]["id"] == change["id"]
    assert (await _decide(client, finance2, supplier.id, change["id"])).status_code == 200


async def test_a_pending_change_changes_nothing_until_approved(
    client: AsyncClient, finance: dict[str, str], finance2: dict[str, str], supplier: Supplier
) -> None:
    change = (await _request(client, finance, supplier.id, _sepa_body())).json()
    await _decide(client, finance2, supplier.id, change["id"])
    await _request(client, finance, supplier.id, _sepa_body(iban=FRENCH_IBAN, bank_country="FR"))

    overview = (await client.get(_url(supplier.id), headers=finance)).json()

    assert overview["current"]["iban"] == GERMAN_IBAN
    assert overview["pending"]["iban"] == FRENCH_IBAN


async def test_only_one_change_can_wait_at_a_time_and_an_identical_one_is_refused(
    client: AsyncClient, finance: dict[str, str], finance2: dict[str, str], supplier: Supplier
) -> None:
    first = (await _request(client, finance, supplier.id, _sepa_body())).json()
    second_while_waiting = await _request(client, finance2, supplier.id, _sepa_body(bic=None))
    await _decide(client, finance2, supplier.id, first["id"])
    same_as_current = await _request(client, finance, supplier.id, _sepa_body())

    assert second_while_waiting.status_code == 409
    assert same_as_current.status_code == 422


async def test_a_decided_change_cannot_be_decided_again(
    client: AsyncClient, finance: dict[str, str], finance2: dict[str, str], supplier: Supplier
) -> None:
    change = (await _request(client, finance, supplier.id, _sepa_body())).json()
    await _decide(client, finance2, supplier.id, change["id"])

    again = await _decide(client, finance2, supplier.id, change["id"])
    reject_after = await _decide(client, finance2, supplier.id, change["id"], "reject")

    assert (again.status_code, reject_after.status_code) == (409, 409)


async def test_rejecting_keeps_it_in_the_history_and_frees_the_slot(
    client: AsyncClient, finance: dict[str, str], finance2: dict[str, str], supplier: Supplier
) -> None:
    change = (await _request(client, finance, supplier.id, _sepa_body())).json()

    withdrawn = await _decide(client, finance, supplier.id, change["id"], "reject")
    overview = (await client.get(_url(supplier.id), headers=finance)).json()
    retry = await _request(client, finance, supplier.id, _sepa_body())

    assert withdrawn.json()["status"] == "rejected"
    assert overview["current"] is None
    assert [row["status"] for row in overview["history"]] == ["rejected"]
    assert retry.status_code == 201


async def test_a_change_of_another_supplier_cannot_be_decided_through_this_one(
    client: AsyncClient,
    finance: dict[str, str],
    finance2: dict[str, str],
    supplier: Supplier,
    db_session: AsyncSession,
) -> None:
    other = Supplier(name="Other Co")
    db_session.add(other)
    await db_session.commit()
    change = (await _request(client, finance, other.id, _sepa_body())).json()

    response = await _decide(client, finance2, supplier.id, change["id"])

    assert response.status_code == 404
    assert (await _decide(client, finance2, supplier.id, 9999)).status_code == 404


@pytest.mark.parametrize(
    "overrides",
    [
        {"iban": "DE89370400440532013001"},  # bad checksum
        {"iban": "FR1420041010050500013M02606"},  # not the bank country (DE)
        {"bic": "NOTABIC"},
        {"iban": None, "bic": None},  # no account at all
        {"iban": None, "bank_account_number": "12345678", "routing_number": "021000022"},  # bad ABA checksum
        {"iban": None, "bank_account_number": None, "routing_number": VALID_ROUTING},  # routing without an account
        {"bank_country": "Germany"},
        {"bank_account_name": ""},
    ],
)
async def test_bank_identifiers_are_validated_when_entered(
    client: AsyncClient, finance: dict[str, str], supplier: Supplier, overrides: dict[str, Any]
) -> None:
    response = await _request(client, finance, supplier.id, _sepa_body(**overrides))

    assert response.status_code == 422


async def test_identifiers_are_stored_without_spaces_and_in_capitals(
    client: AsyncClient, finance: dict[str, str], supplier: Supplier
) -> None:
    body = _sepa_body(iban="de89 3704 0044 0532 0130 00", bic="cobadeffxxx")

    created = await _request(client, finance, supplier.id, body)

    assert (created.json()["iban"], created.json()["bic"]) == (GERMAN_IBAN, "COBADEFFXXX")


async def test_us_details_with_routing_and_account_number_are_accepted(
    client: AsyncClient, finance: dict[str, str], supplier: Supplier
) -> None:
    body = {
        "bank_account_name": "Test Supplier Inc",
        "bank_country": "US",
        "bank_account_number": "000123456789",
        "routing_number": VALID_ROUTING,
    }

    response = await _request(client, finance, supplier.id, body)

    assert response.status_code == 201
    assert response.json()["routing_number"] == VALID_ROUTING


async def test_only_holders_of_the_permission_can_see_or_change_bank_details(
    client: AsyncClient, auth_headers: AuthHeaders, finance: dict[str, str], supplier: Supplier
) -> None:
    change = (await _request(client, finance, supplier.id, _sepa_body())).json()
    calls = [
        ("GET", _url(supplier.id), None),
        ("POST", _url(supplier.id, "/changes"), _sepa_body()),
        ("POST", _url(supplier.id, f"/changes/{change['id']}/approve"), {}),
        ("POST", _url(supplier.id, f"/changes/{change['id']}/reject"), {}),
    ]

    for role in ("viewer", "purchasing_officer", "warehouse_manager", "employee"):
        headers = await auth_headers(role)
        for method, url, body in calls:
            assert (await client.request(method, url, json=body, headers=headers)).status_code == 403
    for method, url, body in calls:
        assert (await client.request(method, url, json=body)).status_code == 401


async def test_the_audit_log_masks_the_account_number(
    client: AsyncClient, finance: dict[str, str], finance2: dict[str, str], supplier: Supplier, db_session: AsyncSession
) -> None:
    change = (await _request(client, finance, supplier.id, _sepa_body())).json()
    await _decide(client, finance2, supplier.id, change["id"])

    entries = (
        (
            await db_session.execute(
                select(AuditLog).where(AuditLog.action.like("supplier_bank_change_%")).order_by(AuditLog.id)
            )
        )
        .scalars()
        .all()
    )

    assert [entry.action for entry in entries] == ["supplier_bank_change_requested", "supplier_bank_change_approved"]
    assert GERMAN_IBAN not in json.dumps([entry.extra_data for entry in entries])
    assert entries[0].extra_data is not None
    assert entries[0].extra_data["account_tail"] == "...3000"
    assert entries[1].user_id != entries[0].user_id


async def test_other_holders_are_notified_but_not_the_requester(
    client: AsyncClient, finance: dict[str, str], finance2: dict[str, str], supplier: Supplier, db_session: AsyncSession
) -> None:
    await _request(client, finance, supplier.id, _sepa_body())

    recipients = (await db_session.execute(select(Notification.user_id))).scalars().all()
    requester_notifications = await db_session.scalar(
        select(func.count()).select_from(Notification).where(Notification.message.like("%awaiting approval%"))
    )

    assert requester_notifications == len(recipients)
    # finance2 exists as a holder; finance (the requester) must not be among the recipients.
    me = (await client.get(f"{API}/auth/me", headers=finance)).json()["id"]
    assert me not in recipients


async def test_the_database_allows_one_current_version_per_supplier(
    client: AsyncClient, finance: dict[str, str], finance2: dict[str, str], supplier: Supplier, db_session: AsyncSession
) -> None:
    for iban, country in ((GERMAN_IBAN, "DE"), (FRENCH_IBAN, "FR")):
        change = (await _request(client, finance, supplier.id, _sepa_body(iban=iban, bank_country=country))).json()
        await _decide(client, finance2, supplier.id, change["id"])

    states = (
        (
            await db_session.execute(
                select(SupplierBankDetails.status).where(SupplierBankDetails.supplier_id == supplier.id)
            )
        )
        .scalars()
        .all()
    )

    assert sorted(states) == ["current", "superseded"]
