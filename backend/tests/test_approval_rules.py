from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from tests.fixture_types import AuthHeaders
from tests.flow_helpers import API, add_rule, role_id

RULES_URL = f"{API}/approval-rules"


async def test_rules_require_sign_in(client: AsyncClient) -> None:
    assert (await client.get(RULES_URL)).status_code == 401


@pytest.mark.parametrize(
    "role", ["viewer", "employee", "procurement_manager", "purchasing_officer", "department_manager"]
)
async def test_only_people_who_manage_approvals_can_see_or_change_rules(
    client: AsyncClient, auth_headers: AuthHeaders, role: str
) -> None:
    finance = await auth_headers("finance")
    headers = await auth_headers(role)
    rule_id = (await add_rule(client, finance, document_type="purchase_order", roles=["procurement_manager"])).json()[
        "id"
    ]

    listed = await client.get(RULES_URL, headers=headers)
    created = await add_rule(
        client, headers, document_type="purchase_order", roles=["procurement_manager"], min_amount="5000"
    )
    updated = await client.patch(f"{RULES_URL}/{rule_id}", json={"name": "Hijacked"}, headers=headers)
    deleted = await client.delete(f"{RULES_URL}/{rule_id}", headers=headers)

    assert {listed.status_code, created.status_code, updated.status_code, deleted.status_code} == {403}


async def test_finance_creates_a_rule_with_ordered_steps_and_it_is_audited(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession
) -> None:
    finance = await auth_headers("finance")

    response = await add_rule(
        client,
        finance,
        document_type="purchase_order",
        roles=["department_manager", "procurement_manager", "finance"],
        min_amount="1000",
        max_amount="50000",
        name="Mid-size orders",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Mid-size orders"
    assert body["min_amount"] == "1000.00"
    assert body["max_amount"] == "50000.00"
    assert [step["step_order"] for step in body["steps"]] == [1, 2, 3]
    assert [step["approver_role_id"] for step in body["steps"]] == [
        await role_id(client, finance, name) for name in ("department_manager", "procurement_manager", "finance")
    ]
    audit = await db_session.scalar(select(AuditLog).where(AuditLog.action == "approval_rule_created"))
    assert audit is not None
    assert audit.extra_data is not None
    assert audit.extra_data["name"] == "Mid-size orders"


async def test_a_rule_can_name_a_role_that_does_not_hold_the_approve_permission(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    finance = await auth_headers("finance")

    response = await add_rule(client, finance, document_type="purchase_order", roles=["finance"])

    assert response.status_code == 201


@pytest.mark.parametrize(
    "overrides",
    [
        {"min_amount": "-1"},
        {"min_amount": "100", "max_amount": "100"},
        {"min_amount": "100", "max_amount": "50"},
        {"name": ""},
        {"steps": []},
        {"steps": [{"approver_role_id": 9999}]},
        {"document_type": "payroll"},
    ],
)
async def test_invalid_rules_are_rejected(
    client: AsyncClient, auth_headers: AuthHeaders, overrides: dict[str, Any]
) -> None:
    finance = await auth_headers("finance")
    pm = await role_id(client, finance, "procurement_manager")
    payload: dict[str, Any] = {
        "name": "Rule",
        "document_type": "purchase_order",
        "min_amount": "0",
        "max_amount": None,
        "steps": [{"approver_role_id": pm}],
        **overrides,
    }

    response = await client.post(RULES_URL, json=payload, headers=finance)

    assert response.status_code in {400, 422}


async def test_too_many_steps_are_rejected(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    finance = await auth_headers("finance")

    response = await add_rule(client, finance, document_type="purchase_order", roles=["finance"] * 6)

    assert response.status_code == 422


async def test_active_rules_for_one_document_type_cannot_overlap(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    finance = await auth_headers("finance")
    await add_rule(
        client, finance, document_type="purchase_order", roles=["procurement_manager"], max_amount="1000", name="Small"
    )

    overlapping = await add_rule(
        client, finance, document_type="purchase_order", roles=["finance"], min_amount="500", max_amount="2000"
    )
    touching = await add_rule(client, finance, document_type="purchase_order", roles=["finance"], min_amount="1000")

    assert overlapping.status_code == 409
    assert "Small" in overlapping.json()["detail"]
    # Bands are half-open: one that starts exactly where the other ends does not overlap it.
    assert touching.status_code == 201


async def test_overlap_is_checked_per_document_type_and_ignores_inactive_rules(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    finance = await auth_headers("finance")
    await add_rule(client, finance, document_type="purchase_order", roles=["procurement_manager"], name="Orders")

    other_type = await add_rule(client, finance, document_type="purchase_request", roles=["department_manager"])
    inactive = await add_rule(
        client, finance, document_type="purchase_order", roles=["finance"], is_active=False, name="Draft rule"
    )

    assert other_type.status_code == 201
    assert inactive.status_code == 201


async def test_reactivating_a_rule_is_checked_for_overlap(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    finance = await auth_headers("finance")
    await add_rule(client, finance, document_type="purchase_order", roles=["procurement_manager"])
    dormant = (
        await add_rule(client, finance, document_type="purchase_order", roles=["finance"], is_active=False)
    ).json()["id"]

    response = await client.patch(f"{RULES_URL}/{dormant}", json={"is_active": True}, headers=finance)

    assert response.status_code == 409


async def test_a_rule_can_be_edited_including_its_steps(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    finance = await auth_headers("finance")
    rule_id = (await add_rule(client, finance, document_type="purchase_order", roles=["procurement_manager"])).json()[
        "id"
    ]
    finance_role = await role_id(client, finance, "finance")
    pm_role = await role_id(client, finance, "procurement_manager")

    response = await client.patch(
        f"{RULES_URL}/{rule_id}",
        json={
            "name": "Two steps",
            "max_amount": "9999",
            "steps": [{"approver_role_id": pm_role}, {"approver_role_id": finance_role}],
        },
        headers=finance,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Two steps"
    assert body["max_amount"] == "9999.00"
    assert [(s["step_order"], s["approver_role_id"]) for s in body["steps"]] == [(1, pm_role), (2, finance_role)]


async def test_an_edit_cannot_make_the_band_empty(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    finance = await auth_headers("finance")
    rule_id = (
        await add_rule(
            client, finance, document_type="purchase_order", roles=["finance"], min_amount="100", max_amount="500"
        )
    ).json()["id"]

    response = await client.patch(f"{RULES_URL}/{rule_id}", json={"min_amount": "500"}, headers=finance)

    assert response.status_code == 422


async def test_required_rule_fields_cannot_be_cleared(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    finance = await auth_headers("finance")
    rule_id = (await add_rule(client, finance, document_type="purchase_order", roles=["finance"])).json()["id"]

    response = await client.patch(f"{RULES_URL}/{rule_id}", json={"name": None}, headers=finance)

    assert response.status_code == 422


async def test_rules_can_be_listed_by_type_and_deleted(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    finance = await auth_headers("finance")
    order_rule = (await add_rule(client, finance, document_type="purchase_order", roles=["finance"])).json()["id"]
    await add_rule(client, finance, document_type="purchase_request", roles=["department_manager"])

    orders = await client.get(RULES_URL, params={"document_type": "purchase_order"}, headers=finance)
    deleted = await client.delete(f"{RULES_URL}/{order_rule}", headers=finance)
    again = await client.delete(f"{RULES_URL}/{order_rule}", headers=finance)

    assert [rule["id"] for rule in orders.json()] == [order_rule]
    assert deleted.status_code == 204
    assert again.status_code == 404
