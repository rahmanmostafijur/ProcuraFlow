from datetime import timedelta
from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_today
from app.models.audit import AuditLog
from app.models.product import Product
from app.models.supplier import Supplier
from tests.fixture_types import AuthHeaders
from tests.flow_helpers import (
    API,
    add_rule,
    approval_steps,
    approve_po,
    get_po,
    queue,
    set_limit,
    submitted_po,
    user_id,
)

DELEGATIONS_URL = f"{API}/approval-delegations"


async def _delegate(
    client: AsyncClient,
    headers: dict[str, str],
    delegate_id: int,
    *,
    starts: int = -1,
    ends: int = 1,
    delegator_id: int | None = None,
) -> Response:
    today = utc_today()
    payload: dict[str, Any] = {
        "delegate_id": delegate_id,
        "starts_on": (today + timedelta(days=starts)).isoformat(),
        "ends_on": (today + timedelta(days=ends)).isoformat(),
    }
    if delegator_id is not None:
        payload["delegator_id"] = delegator_id
    return await client.post(DELEGATIONS_URL, json=payload, headers=headers)


async def test_a_delegate_without_the_role_cannot_approve_until_delegated_to(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    cover = await auth_headers("department_manager")
    po = await submitted_po(client, officer, supplier, product)

    before = await approve_po(client, cover, po["id"])
    await _delegate(client, manager, await user_id(client, cover))
    after = await approve_po(client, cover, po["id"])

    assert before.status_code == 403
    assert after.status_code == 200
    assert after.json()["status"] == "approved"


async def test_a_delegated_decision_records_both_the_delegate_and_the_original_approver(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession, supplier: Supplier, product: Product
) -> None:
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    cover = await auth_headers("department_manager")
    manager_id, cover_id = await user_id(client, manager), await user_id(client, cover)
    await _delegate(client, manager, cover_id)
    po = await submitted_po(client, officer, supplier, product)

    await approve_po(client, cover, po["id"], comment="Covering while away")

    [step] = await approval_steps(client, manager, "purchase_order", po["id"])
    assert step["decided_by"] == cover_id
    assert step["on_behalf_of"] == manager_id
    assert step["decided_by_person"]["full_name"] == "Department_Manager User"
    assert step["on_behalf_of_person"]["full_name"] == "Procurement_Manager User"
    audit = await db_session.scalar(select(AuditLog).where(AuditLog.action == "approval_step_approved"))
    assert audit is not None
    assert audit.user_id == cover_id
    assert audit.extra_data is not None
    assert audit.extra_data["on_behalf_of"] == manager_id
    assert (await get_po(client, cover, po["id"]))["approver"]["id"] == cover_id


async def test_the_queue_shows_what_a_delegate_can_decide_and_for_whom(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    cover = await auth_headers("department_manager")
    po = await submitted_po(client, officer, supplier, product)
    before = await queue(client, cover)
    await _delegate(client, manager, await user_id(client, cover))

    after = await queue(client, cover)

    assert before["total"] == 0
    assert [item["document_id"] for item in after["items"]] == [po["id"]]
    assert after["items"][0]["on_behalf_of"]["full_name"] == "Procurement_Manager User"


async def test_delegation_never_lets_the_creator_approve_their_own_order(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    await _delegate(client, manager, await user_id(client, officer))
    po = await submitted_po(client, officer, supplier, product)

    response = await approve_po(client, officer, po["id"])

    assert response.status_code == 403
    assert "you created" in response.json()["detail"]


async def test_delegation_cannot_be_used_to_approve_a_second_step(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    finance = await auth_headers("finance")
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    other_manager = await auth_headers("procurement_manager", email="pm2@example.com")
    await add_rule(
        client, finance, document_type="purchase_order", roles=["procurement_manager", "procurement_manager"]
    )
    await _delegate(client, other_manager, await user_id(client, manager))
    po = await submitted_po(client, officer, supplier, product)

    await approve_po(client, manager, po["id"])
    second = await approve_po(client, manager, po["id"])

    # Step 2 is open to the manager's own role and to pm2 (who delegated to them), but the manager already
    # approved step 1, so neither route lets them decide it again.
    assert second.status_code == 403


async def test_the_delegators_limit_applies_to_the_delegate(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    finance = await auth_headers("finance")
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    cover = await auth_headers("department_manager")
    await set_limit(client, finance, await user_id(client, manager), "purchase_order", "100.00")
    await _delegate(client, manager, await user_id(client, cover))
    small = await submitted_po(client, officer, supplier, product, quantity=5, unit_price="10.00")
    large = await submitted_po(client, officer, supplier, product, quantity=50, unit_price="10.00")

    over = await approve_po(client, cover, large["id"])
    within = await approve_po(client, cover, small["id"])

    assert over.status_code == 403
    assert within.status_code == 200


async def test_a_delegation_that_has_not_started_or_was_revoked_gives_no_authority(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    cover = await auth_headers("department_manager")
    cover_id = await user_id(client, cover)
    first = await submitted_po(client, officer, supplier, product)
    second = await submitted_po(client, officer, supplier, product)

    future = await _delegate(client, manager, cover_id, starts=2, ends=5)
    not_yet = await approve_po(client, cover, first["id"])
    current = await _delegate(client, manager, cover_id)
    revoked = await client.post(f"{DELEGATIONS_URL}/{current.json()['id']}/revoke", headers=manager)
    after_revoke = await approve_po(client, cover, second["id"])

    assert future.status_code == 201
    assert not_yet.status_code == 403
    assert revoked.status_code == 200
    assert revoked.json()["revoked_at"] is not None
    assert after_revoke.status_code == 403


async def test_a_delegation_cannot_be_created_in_the_past_or_back_to_front(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    manager = await auth_headers("procurement_manager")
    cover = await auth_headers("department_manager")
    cover_id = await user_id(client, cover)

    ended = await _delegate(client, manager, cover_id, starts=-5, ends=-2)
    reversed_dates = await _delegate(client, manager, cover_id, starts=3, ends=1)
    to_self = await _delegate(client, manager, await user_id(client, manager))
    unknown = await _delegate(client, manager, 99999)

    assert ended.status_code == 422
    assert reversed_dates.status_code == 422
    assert to_self.status_code == 422
    assert unknown.status_code == 400


async def test_people_can_only_delegate_their_own_approvals_unless_they_manage_approvals(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    finance = await auth_headers("finance")
    manager = await auth_headers("procurement_manager")
    cover = await auth_headers("department_manager")
    manager_id, cover_id = await user_id(client, manager), await user_id(client, cover)

    refused = await _delegate(client, cover, manager_id, delegator_id=manager_id)
    allowed = await _delegate(client, finance, cover_id, delegator_id=manager_id)

    assert refused.status_code == 403
    assert allowed.status_code == 201
    assert allowed.json()["delegator"]["id"] == manager_id


async def test_delegations_are_visible_only_to_the_people_involved_and_to_approval_managers(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    finance = await auth_headers("finance")
    manager = await auth_headers("procurement_manager")
    cover = await auth_headers("department_manager")
    stranger = await auth_headers("employee")
    created = await _delegate(client, manager, await user_id(client, cover))
    delegation_id = created.json()["id"]

    as_manager = await client.get(DELEGATIONS_URL, headers=manager)
    as_cover = await client.get(DELEGATIONS_URL, headers=cover)
    as_finance = await client.get(DELEGATIONS_URL, headers=finance)
    as_stranger = await client.get(DELEGATIONS_URL, headers=stranger)
    revoke_by_stranger = await client.post(f"{DELEGATIONS_URL}/{delegation_id}/revoke", headers=stranger)

    assert [row["id"] for row in as_manager.json()] == [delegation_id]
    assert [row["id"] for row in as_cover.json()] == [delegation_id]
    assert [row["id"] for row in as_finance.json()] == [delegation_id]
    assert as_stranger.json() == []
    assert revoke_by_stranger.status_code == 404


async def test_only_the_delegator_or_a_manager_can_end_a_delegation(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    manager = await auth_headers("procurement_manager")
    cover = await auth_headers("department_manager")
    delegation_id = (await _delegate(client, manager, await user_id(client, cover))).json()["id"]

    by_delegate = await client.post(f"{DELEGATIONS_URL}/{delegation_id}/revoke", headers=cover)
    by_delegator = await client.post(f"{DELEGATIONS_URL}/{delegation_id}/revoke", headers=manager)

    assert by_delegate.status_code == 403
    assert by_delegator.status_code == 200


async def test_delegations_require_sign_in(client: AsyncClient) -> None:
    assert (await client.get(DELEGATIONS_URL)).status_code == 401
    assert (await client.post(DELEGATIONS_URL, json={})).status_code == 401
