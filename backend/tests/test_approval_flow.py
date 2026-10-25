from typing import Any

from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import ApprovalStep
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

SMALL_ORDER: dict[str, Any] = {"quantity": 5, "unit_price": "10.00"}  # 50.00
LARGE_ORDER: dict[str, Any] = {"quantity": 50, "unit_price": "10.00"}  # 500.00


async def _two_tier_rules(client: AsyncClient, finance: dict[str, str]) -> None:
    await add_rule(
        client, finance, document_type="purchase_order", roles=["procurement_manager"], max_amount="100", name="Small"
    )
    await add_rule(
        client,
        finance,
        document_type="purchase_order",
        roles=["procurement_manager", "finance"],
        min_amount="100",
        name="Large",
    )


async def test_without_rules_one_step_is_decided_by_anyone_with_the_approve_permission(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    po = await submitted_po(client, officer, supplier, product)

    steps = await approval_steps(client, manager, "purchase_order", po["id"])
    approved = await approve_po(client, manager, po["id"])

    assert len(steps) == 1
    assert steps[0]["required_permission"] == "po:approve"
    assert steps[0]["approver_role_id"] is None
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"


async def test_the_matching_rule_decides_how_many_steps_a_document_needs(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    finance = await auth_headers("finance")
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    await _two_tier_rules(client, finance)

    small = await submitted_po(client, officer, supplier, product, **SMALL_ORDER)
    large = await submitted_po(client, officer, supplier, product, **LARGE_ORDER)

    small_steps = await approval_steps(client, manager, "purchase_order", small["id"])
    large_steps = await approval_steps(client, manager, "purchase_order", large["id"])
    assert [step["rule_name"] for step in small_steps] == ["Small"]
    assert [step["rule_name"] for step in large_steps] == ["Large", "Large"]
    assert (await approve_po(client, manager, small["id"])).json()["status"] == "approved"


async def test_a_two_step_order_is_approved_only_after_the_last_step(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession, supplier: Supplier, product: Product
) -> None:
    finance = await auth_headers("finance")
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    await _two_tier_rules(client, finance)
    po = await submitted_po(client, officer, supplier, product, **LARGE_ORDER)

    first = await approve_po(client, manager, po["id"], comment="Looks right")
    middle = await get_po(client, manager, po["id"])
    second = await approve_po(client, finance, po["id"])

    assert first.status_code == 200
    assert first.json()["status"] == "submitted"
    assert middle["approver"] is None
    assert second.status_code == 200
    assert second.json()["status"] == "approved"
    assert second.json()["approver"]["full_name"] == "Finance User"
    steps = await approval_steps(client, finance, "purchase_order", po["id"])
    assert [step["status"] for step in steps] == ["approved", "approved"]
    assert steps[0]["comment"] == "Looks right"
    assert steps[0]["decided_by_person"]["full_name"] == "Procurement_Manager User"
    events = (await db_session.scalars(select(AuditLog.action).where(AuditLog.entity_id == po["id"]))).all()
    assert events.count("approval_step_approved") == 2
    assert events.count("po_approved") == 1


async def test_a_person_without_the_steps_role_cannot_decide_it(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    finance = await auth_headers("finance")
    officer = await auth_headers("purchasing_officer")
    await _two_tier_rules(client, finance)
    po = await submitted_po(client, officer, supplier, product, **LARGE_ORDER)

    # Finance owns step 2, but step 1 belongs to the procurement manager.
    response = await approve_po(client, finance, po["id"])

    assert response.status_code == 403
    assert "procurement manager" in response.json()["detail"]
    assert (await get_po(client, finance, po["id"]))["status"] == "submitted"


async def test_nobody_approves_two_steps_of_the_same_order(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    finance = await auth_headers("finance")
    officer = await auth_headers("purchasing_officer")
    first_manager = await auth_headers("procurement_manager", email="pm1@example.com")
    second_manager = await auth_headers("procurement_manager", email="pm2@example.com")
    await add_rule(
        client, finance, document_type="purchase_order", roles=["procurement_manager", "procurement_manager"]
    )
    po = await submitted_po(client, officer, supplier, product)

    await approve_po(client, first_manager, po["id"])
    again = await approve_po(client, first_manager, po["id"])
    other = await approve_po(client, second_manager, po["id"])

    assert again.status_code == 403
    assert "already approved an earlier step" in again.json()["detail"]
    assert other.status_code == 200
    assert other.json()["status"] == "approved"


async def test_the_creator_cannot_approve_any_step_even_with_the_right_role(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    finance = await auth_headers("finance")
    manager = await auth_headers("procurement_manager")
    await add_rule(client, finance, document_type="purchase_order", roles=["procurement_manager"])
    po = await submitted_po(client, manager, supplier, product)

    response = await approve_po(client, manager, po["id"])

    assert response.status_code == 403
    assert response.json()["detail"] == "You cannot approve a purchase order you created."


async def test_an_approval_limit_stops_a_user_approving_more_than_their_limit(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    finance = await auth_headers("finance")
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    director = await auth_headers("admin")
    await set_limit(client, finance, await user_id(client, manager), "purchase_order", "100.00")
    small = await submitted_po(client, officer, supplier, product, **SMALL_ORDER)
    large = await submitted_po(client, officer, supplier, product, **LARGE_ORDER)

    over = await approve_po(client, manager, large["id"])
    within = await approve_po(client, manager, small["id"])
    unlimited = await approve_po(client, director, large["id"])

    assert over.status_code == 403
    assert "approval limit for purchase orders is 100.00 USD" in over.json()["detail"]
    assert "500.00 USD" in over.json()["detail"]
    assert within.status_code == 200
    assert unlimited.status_code == 200


async def test_limits_are_per_document_type(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    finance = await auth_headers("finance")
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    await set_limit(client, finance, await user_id(client, manager), "purchase_request", "1.00")
    po = await submitted_po(client, officer, supplier, product, **LARGE_ORDER)

    response = await approve_po(client, manager, po["id"])

    assert response.status_code == 200


async def test_limits_can_be_managed_only_by_people_who_manage_approvals(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    finance = await auth_headers("finance")
    manager = await auth_headers("procurement_manager")
    manager_id = await user_id(client, manager)

    refused = await set_limit(client, manager, manager_id, "purchase_order", "1000000")
    created = await set_limit(client, finance, manager_id, "purchase_order", "5000")
    updated = await set_limit(client, finance, manager_id, "purchase_order", "7500")
    mine = await client.get(f"{API}/approval-limits", headers=manager)
    everyone = await client.get(f"{API}/approval-limits", headers=finance)
    removed = await client.delete(f"{API}/approval-limits/{created.json()['id']}", headers=finance)

    assert refused.status_code == 403
    assert created.status_code == 200
    assert updated.json()["id"] == created.json()["id"]
    assert updated.json()["max_amount"] == "7500.00"
    assert [limit["user_id"] for limit in mine.json()] == [manager_id]
    assert len(everyone.json()) == 1
    assert removed.status_code == 204


async def test_a_negative_or_unknown_limit_is_rejected(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    finance = await auth_headers("finance")

    negative = await set_limit(client, finance, 1, "purchase_order", "-5")
    unknown_user = await set_limit(client, finance, 99999, "purchase_order", "5")

    assert negative.status_code == 422
    assert unknown_user.status_code == 400


async def test_rejecting_cancels_the_order_keeps_the_reason_and_skips_the_remaining_steps(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession, supplier: Supplier, product: Product
) -> None:
    finance = await auth_headers("finance")
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    await _two_tier_rules(client, finance)
    po = await submitted_po(client, officer, supplier, product, **LARGE_ORDER)

    response = await client.post(
        f"{API}/purchase-orders/{po['id']}/reject", json={"comment": "Over budget for this quarter"}, headers=manager
    )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    steps = await approval_steps(client, manager, "purchase_order", po["id"])
    assert [step["status"] for step in steps] == ["rejected", "skipped"]
    assert steps[0]["comment"] == "Over budget for this quarter"
    audit = await db_session.scalar(select(AuditLog).where(AuditLog.action == "po_rejected"))
    assert audit is not None
    assert audit.extra_data == {"reason": "Over budget for this quarter"}


async def test_a_rejection_needs_a_reason(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    po = await submitted_po(client, officer, supplier, product)

    blank = await client.post(f"{API}/purchase-orders/{po['id']}/reject", json={"comment": "   "}, headers=manager)
    missing = await client.post(f"{API}/purchase-orders/{po['id']}/reject", json={}, headers=manager)

    assert blank.status_code == 422
    assert missing.status_code == 422
    assert (await get_po(client, manager, po["id"]))["status"] == "submitted"


async def test_an_order_that_is_not_waiting_cannot_be_approved_or_rejected(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    draft = (
        await client.post(
            f"{API}/purchase-orders",
            json={"supplier_id": supplier.id, "items": [{"product_id": product.id, "quantity": 1, "unit_price": "1"}]},
            headers=officer,
        )
    ).json()

    approve = await approve_po(client, manager, draft["id"])
    reject = await client.post(f"{API}/purchase-orders/{draft['id']}/reject", json={"comment": "no"}, headers=manager)

    assert approve.status_code == 409
    assert reject.status_code == 409


async def test_the_queue_lists_only_what_the_user_could_decide_right_now(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    finance = await auth_headers("finance")
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    viewer = await auth_headers("viewer")
    await _two_tier_rules(client, finance)
    small = await submitted_po(client, officer, supplier, product, **SMALL_ORDER)
    large = await submitted_po(client, officer, supplier, product, **LARGE_ORDER)

    manager_queue = await queue(client, manager)
    finance_before = await queue(client, finance)
    officer_queue = await queue(client, officer)
    viewer_queue = await queue(client, viewer)
    await approve_po(client, manager, large["id"])
    finance_after = await queue(client, finance)
    manager_after = await queue(client, manager)

    assert {item["document_id"] for item in manager_queue["items"]} == {small["id"], large["id"]}
    assert manager_queue["total"] == 2
    item = next(entry for entry in manager_queue["items"] if entry["document_id"] == large["id"])
    assert (item["document_type"], item["label"], item["amount_base"], item["step_order"], item["steps_total"]) == (
        "purchase_order",
        large["po_number"],
        "500.00",
        1,
        2,
    )
    # Finance is not asked until the manager has decided step 1.
    assert finance_before["total"] == 0
    assert [entry["document_id"] for entry in finance_after["items"]] == [large["id"]]
    assert finance_after["items"][0]["step_order"] == 2
    # The creator never sees their own orders, and a viewer has nothing to decide.
    assert officer_queue["total"] == 0
    assert viewer_queue["total"] == 0
    assert [entry["document_id"] for entry in manager_after["items"]] == [small["id"]]


async def test_the_queue_is_paged_and_its_total_is_the_full_count(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    for _ in range(3):
        await submitted_po(client, officer, supplier, product)

    page = await client.get(f"{API}/approvals/queue", params={"page": 2, "page_size": 2}, headers=manager)

    assert page.json()["total"] == 3
    assert len(page.json()["items"]) == 1


async def test_the_queue_requires_sign_in(client: AsyncClient) -> None:
    assert (await client.get(f"{API}/approvals/queue")).status_code == 401


async def test_orders_submitted_before_rules_existed_still_get_a_single_step(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession, supplier: Supplier, product: Product
) -> None:
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    po = await submitted_po(client, officer, supplier, product)
    # What a submitted order looked like before this feature: no step rows at all.
    await db_session.execute(delete(ApprovalStep))
    await db_session.commit()

    approved = await approve_po(client, manager, po["id"])

    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert len(await approval_steps(client, manager, "purchase_order", po["id"])) == 1


async def test_an_unknown_document_has_no_history(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    manager = await auth_headers("procurement_manager")

    response = await client.get(f"{API}/approvals/purchase_order/99999/steps", headers=manager)

    assert response.status_code == 404
