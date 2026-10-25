from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from tests.fixture_types import AuthHeaders

URL = "/api/v1/tax-rates"
VAT_20: dict[str, Any] = {"name": "Test VAT 20%", "percentage": "20", "tax_type": "vat"}


async def test_tax_rates_require_sign_in(client: AsyncClient) -> None:
    assert (await client.get(URL)).status_code == 401


async def test_finance_creates_a_rate_and_anyone_can_list_it(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    finance = await auth_headers("finance")
    viewer = await auth_headers("viewer")

    created = await client.post(URL, json={**VAT_20, "region": "de"}, headers=finance)
    listed = await client.get(URL, headers=viewer)

    assert created.status_code == 201
    body = created.json()
    assert body["percentage"] == "20.0000"
    assert body["tax_type"] == "vat"
    assert body["region"] == "DE"
    assert body["is_inclusive"] is False
    assert body["is_reverse_charge"] is False
    assert body["is_active"] is True
    assert [row["name"] for row in listed.json()] == ["Test VAT 20%"]


async def test_creating_a_rate_is_audited(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession
) -> None:
    headers = await auth_headers("finance")
    tax_rate_id = (await client.post(URL, json=VAT_20, headers=headers)).json()["id"]

    audit = await db_session.scalar(select(AuditLog).where(AuditLog.action == "tax_rate_created"))

    assert audit is not None
    assert audit.entity_id == tax_rate_id


async def test_duplicate_names_conflict(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("finance")
    await client.post(URL, json=VAT_20, headers=headers)

    response = await client.post(URL, json=VAT_20, headers=headers)

    assert response.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {**VAT_20, "percentage": "-1"},
        {**VAT_20, "percentage": "100.01"},
        {**VAT_20, "percentage": "19.00001"},
        {**VAT_20, "name": ""},
        {**VAT_20, "tax_type": "gst"},
        {**VAT_20, "is_reverse_charge": True},
    ],
)
async def test_invalid_rates_are_rejected(
    client: AsyncClient, auth_headers: AuthHeaders, payload: dict[str, Any]
) -> None:
    headers = await auth_headers("finance")

    response = await client.post(URL, json=payload, headers=headers)

    assert response.status_code == 422


async def test_a_reverse_charge_rate_is_zero_percent(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("finance")

    response = await client.post(
        URL,
        json={"name": "EU reverse charge", "percentage": "0", "tax_type": "vat", "is_reverse_charge": True},
        headers=headers,
    )

    assert response.status_code == 201
    assert response.json()["is_reverse_charge"] is True


@pytest.mark.parametrize("role", ["viewer", "procurement_manager", "purchasing_officer", "warehouse_manager"])
async def test_only_finance_can_change_tax_rates(client: AsyncClient, auth_headers: AuthHeaders, role: str) -> None:
    finance = await auth_headers("finance")
    tax_rate_id = (await client.post(URL, json=VAT_20, headers=finance)).json()["id"]
    headers = await auth_headers(role)

    create = await client.post(URL, json={**VAT_20, "name": "Other"}, headers=headers)
    update = await client.patch(f"{URL}/{tax_rate_id}", json={"percentage": "25"}, headers=headers)

    assert create.status_code == 403
    assert update.status_code == 403


async def test_a_rate_can_be_edited_and_retired(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession
) -> None:
    headers = await auth_headers("finance")
    tax_rate_id = (await client.post(URL, json=VAT_20, headers=headers)).json()["id"]

    edited = await client.patch(
        f"{URL}/{tax_rate_id}", json={"percentage": "21", "is_inclusive": True}, headers=headers
    )
    retired = await client.patch(f"{URL}/{tax_rate_id}", json={"is_active": False}, headers=headers)
    active = await client.get(URL, params={"active_only": True}, headers=headers)

    assert edited.json()["percentage"] == "21.0000"
    assert edited.json()["is_inclusive"] is True
    assert retired.json()["is_active"] is False
    assert active.json() == []
    audit = await db_session.scalar(
        select(AuditLog).where(AuditLog.action == "tax_rate_updated").order_by(AuditLog.id).limit(1)
    )
    assert audit is not None
    assert audit.extra_data is not None
    change = audit.extra_data["changes"]["percentage"]
    assert (Decimal(change["from"]), Decimal(change["to"])) == (Decimal(20), Decimal(21))


async def test_an_edit_cannot_leave_a_reverse_charge_rate_taxed(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("finance")
    tax_rate_id = (await client.post(URL, json=VAT_20, headers=headers)).json()["id"]

    flag_only = await client.patch(f"{URL}/{tax_rate_id}", json={"is_reverse_charge": True}, headers=headers)

    assert flag_only.status_code == 422


async def test_required_fields_cannot_be_cleared(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("finance")
    tax_rate_id = (await client.post(URL, json=VAT_20, headers=headers)).json()["id"]

    response = await client.patch(f"{URL}/{tax_rate_id}", json={"percentage": None}, headers=headers)

    assert response.status_code == 422


async def test_renaming_to_an_existing_name_conflicts(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("finance")
    await client.post(URL, json=VAT_20, headers=headers)
    other_id = (await client.post(URL, json={**VAT_20, "name": "Other"}, headers=headers)).json()["id"]

    response = await client.patch(f"{URL}/{other_id}", json={"name": VAT_20["name"]}, headers=headers)

    assert response.status_code == 409


async def test_editing_an_unknown_rate_is_404(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("finance")

    response = await client.patch(f"{URL}/9999", json={"percentage": "5"}, headers=headers)

    assert response.status_code == 404
