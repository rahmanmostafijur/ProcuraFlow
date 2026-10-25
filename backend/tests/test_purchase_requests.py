import re
from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_today
from app.models.product import Product
from app.models.supplier import Supplier
from tests.fixture_types import AuthHeaders
from tests.flow_helpers import API, add_rule, approval_steps, queue, user_id

REQUESTS_URL = f"{API}/purchase-requests"
LINE: dict[str, Any] = {"description": "Standing desk", "quantity": 2, "estimated_unit_price": "450.00"}


async def _create(client: AsyncClient, headers: dict[str, str], **overrides: Any) -> Response:
    payload: dict[str, Any] = {"title": "Desks for the new office", "lines": [LINE], **overrides}
    return await client.post(REQUESTS_URL, json=payload, headers=headers)


async def _submitted(client: AsyncClient, headers: dict[str, str], **overrides: Any) -> dict[str, Any]:
    request = (await _create(client, headers, **overrides)).json()
    response = await client.post(f"{REQUESTS_URL}/{request['id']}/submit", headers=headers)
    assert response.status_code == 200, response.text
    return dict(response.json())


async def _approved(
    client: AsyncClient, requester: dict[str, str], approver: dict[str, str], **overrides: Any
) -> dict[str, Any]:
    request = await _submitted(client, requester, **overrides)
    response = await client.post(f"{REQUESTS_URL}/{request['id']}/approve", headers=approver)
    assert response.status_code == 200, response.text
    return dict(response.json())


async def test_an_employee_creates_a_request_with_priced_lines(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    employee = await auth_headers("employee")

    response = await _create(
        client,
        employee,
        notes="Replacing the old ones",
        lines=[LINE, {"description": "Cable tray", "quantity": 3, "unit": "box", "estimated_unit_price": "12.3333"}],
    )

    assert response.status_code == 201
    body = response.json()
    assert re.fullmatch(r"PR-\d{4}-\d{5}", body["request_number"])
    assert (body["status"], body["currency_code"], body["requester"]["full_name"]) == (
        "draft",
        "USD",
        "Employee User",
    )
    assert [line["line_total"] for line in body["lines"]] == ["900.00", "37.00"]
    assert body["estimated_total"] == "937.00"
    assert body["base_estimated_total"] is None


async def test_a_viewer_cannot_create_a_request(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    viewer = await auth_headers("viewer")

    assert (await _create(client, viewer)).status_code == 403


async def test_requests_require_sign_in(client: AsyncClient) -> None:
    assert (await client.get(REQUESTS_URL)).status_code == 401
    assert (await client.post(REQUESTS_URL, json={})).status_code == 401


@pytest.mark.parametrize(
    "overrides",
    [
        {"lines": []},
        {"title": ""},
        {"lines": [{**LINE, "quantity": 0}]},
        {"lines": [{**LINE, "estimated_unit_price": "-1"}]},
        {"lines": [{**LINE, "estimated_unit_price": "1.23456"}]},
        {"lines": [{"description": "No price", "quantity": 1}]},
        {"lines": [{**LINE, "description": ""}]},
    ],
)
async def test_invalid_requests_are_rejected(
    client: AsyncClient, auth_headers: AuthHeaders, overrides: dict[str, Any]
) -> None:
    employee = await auth_headers("employee")

    response = await _create(client, employee, **overrides)

    assert response.status_code == 422


async def test_unknown_references_are_rejected(
    client: AsyncClient, auth_headers: AuthHeaders, product: Product
) -> None:
    employee = await auth_headers("employee")

    bad_product = await _create(client, employee, lines=[{**LINE, "product_id": 99999}])
    bad_supplier = await _create(client, employee, lines=[{**LINE, "supplier_id": 99999}])
    bad_cost_centre = await _create(client, employee, cost_centre_id=99999)
    inactive_currency = await _create(client, employee, currency_code="JPY")

    assert {bad_product.status_code, bad_supplier.status_code, bad_cost_centre.status_code} == {400}
    assert inactive_currency.status_code == 400


async def test_requests_are_visible_only_to_their_owner_and_to_people_who_see_everything(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    alice = await auth_headers("employee", email="alice@example.com")
    bob = await auth_headers("employee", email="bob@example.com")
    officer = await auth_headers("purchasing_officer")
    request_id = (await _create(client, alice)).json()["id"]

    own = await client.get(f"{REQUESTS_URL}/{request_id}", headers=alice)
    other_employee = await client.get(f"{REQUESTS_URL}/{request_id}", headers=bob)
    reader = await client.get(f"{REQUESTS_URL}/{request_id}", headers=officer)
    bobs_list = await client.get(REQUESTS_URL, headers=bob)
    officers_list = await client.get(REQUESTS_URL, headers=officer)
    officers_own = await client.get(REQUESTS_URL, params={"mine": True}, headers=officer)

    assert own.status_code == 200
    assert other_employee.status_code == 404
    assert reader.status_code == 200
    assert bobs_list.json()["total"] == 0
    assert officers_list.json()["total"] == 1
    assert officers_own.json()["total"] == 0


async def test_another_employee_cannot_change_submit_cancel_or_decide_a_request(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    alice = await auth_headers("employee", email="alice@example.com")
    bob = await auth_headers("employee", email="bob@example.com")
    request_id = (await _create(client, alice)).json()["id"]
    url = f"{REQUESTS_URL}/{request_id}"

    results = [
        await client.patch(url, json={"title": "Mine now"}, headers=bob),
        await client.post(f"{url}/submit", headers=bob),
        await client.post(f"{url}/cancel", headers=bob),
        await client.post(f"{url}/approve", headers=bob),
        await client.post(f"{url}/reject", json={"comment": "no"}, headers=bob),
    ]

    assert [result.status_code for result in results] == [404] * 5
    assert (await client.get(url, headers=alice)).json()["title"] == "Desks for the new office"


async def test_the_owner_can_edit_a_draft_and_totals_follow(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    employee = await auth_headers("employee")
    request_id = (await _create(client, employee)).json()["id"]

    response = await client.patch(
        f"{REQUESTS_URL}/{request_id}",
        json={"title": "Fewer desks", "lines": [{**LINE, "quantity": 1}]},
        headers=employee,
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Fewer desks"
    assert response.json()["estimated_total"] == "450.00"
    assert len(response.json()["lines"]) == 1


async def test_changing_the_currency_re_rounds_the_kept_lines(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    finance = await auth_headers("finance")
    employee = await auth_headers("employee")
    await client.patch(f"{API}/currencies/JPY", json={"is_active": True}, headers=finance)
    request_id = (
        await _create(client, employee, lines=[{**LINE, "quantity": 3, "estimated_unit_price": "333.5"}])
    ).json()["id"]

    response = await client.patch(f"{REQUESTS_URL}/{request_id}", json={"currency_code": "JPY"}, headers=employee)

    assert response.status_code == 200
    assert response.json()["currency_code"] == "JPY"
    # 3 x 333.5 = 1000.5, rounded half-up to a whole yen.
    assert response.json()["lines"][0]["line_total"] == "1001.00"


async def test_a_submitted_request_can_no_longer_be_edited(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    employee = await auth_headers("employee")
    request = await _submitted(client, employee)

    response = await client.patch(f"{REQUESTS_URL}/{request['id']}", json={"title": "Changed"}, headers=employee)

    assert response.status_code == 409


async def test_submitting_opens_the_approval_and_fixes_the_base_amount(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    employee = await auth_headers("employee")
    manager = await auth_headers("department_manager")

    request = await _submitted(client, employee)
    steps = await approval_steps(client, employee, "purchase_request", request["id"])
    waiting = await queue(client, manager)

    assert request["status"] == "submitted"
    assert request["base_estimated_total"] == "900.00"
    assert request["submitted_at"] is not None
    assert [(step["required_permission"], step["status"]) for step in steps] == [("request:approve", "pending")]
    assert [(item["document_type"], item["label"]) for item in waiting["items"]] == [
        ("purchase_request", request["request_number"])
    ]


async def test_a_foreign_currency_request_is_converted_at_submission(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    finance = await auth_headers("finance")
    employee = await auth_headers("employee")
    await client.post(
        f"{API}/exchange-rates",
        json={"currency_code": "EUR", "rate": "1.25", "effective_date": utc_today().isoformat()},
        headers=finance,
    )

    request = await _submitted(client, employee, currency_code="EUR")

    assert request["estimated_total"] == "900.00"
    assert request["base_estimated_total"] == "1125.00"


async def test_a_foreign_currency_request_without_a_rate_cannot_be_submitted(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    employee = await auth_headers("employee")
    request_id = (await _create(client, employee, currency_code="EUR")).json()["id"]

    response = await client.post(f"{REQUESTS_URL}/{request_id}/submit", headers=employee)

    assert response.status_code == 409
    assert "exchange rate" in response.json()["detail"]
    assert (await client.get(f"{REQUESTS_URL}/{request_id}", headers=employee)).json()["status"] == "draft"


async def test_rules_for_requests_are_matched_on_the_base_amount(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    finance = await auth_headers("finance")
    employee = await auth_headers("employee")
    manager = await auth_headers("department_manager")
    await add_rule(
        client, finance, document_type="purchase_request", roles=["department_manager"], max_amount="500", name="Small"
    )
    await add_rule(
        client,
        finance,
        document_type="purchase_request",
        roles=["department_manager", "procurement_manager"],
        min_amount="500",
        name="Big",
    )

    small = await _submitted(client, employee, lines=[{**LINE, "quantity": 1}])
    big = await _submitted(client, employee)

    assert [s["rule_name"] for s in await approval_steps(client, manager, "purchase_request", small["id"])] == ["Small"]
    assert [s["rule_name"] for s in await approval_steps(client, manager, "purchase_request", big["id"])] == [
        "Big",
        "Big",
    ]


async def test_a_department_manager_approves_a_request(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    employee = await auth_headers("employee")
    manager = await auth_headers("department_manager")
    request = await _submitted(client, employee)

    response = await client.post(
        f"{REQUESTS_URL}/{request['id']}/approve", json={"comment": "Go ahead"}, headers=manager
    )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["decided_at"] is not None


async def test_nobody_approves_a_request_they_raised(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    manager = await auth_headers("department_manager")
    request = await _submitted(client, manager)

    response = await client.post(f"{REQUESTS_URL}/{request['id']}/approve", headers=manager)

    assert response.status_code == 403
    assert response.json()["detail"] == "You cannot approve a purchase request you created."


async def test_a_role_without_the_approve_permission_cannot_approve(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    employee = await auth_headers("employee")
    officer = await auth_headers("purchasing_officer")
    request = await _submitted(client, employee)

    # The officer can read every request but is not an approver.
    response = await client.post(f"{REQUESTS_URL}/{request['id']}/approve", headers=officer)

    assert response.status_code == 403
    assert "request:approve" in response.json()["detail"]


async def test_a_draft_request_cannot_be_approved(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    employee = await auth_headers("employee")
    manager = await auth_headers("department_manager")
    request_id = (await _create(client, employee)).json()["id"]

    response = await client.post(f"{REQUESTS_URL}/{request_id}/approve", headers=manager)

    assert response.status_code == 409


async def test_rejecting_sends_it_back_and_a_resubmission_starts_a_new_round(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    employee = await auth_headers("employee")
    manager = await auth_headers("department_manager")
    request = await _submitted(client, employee)

    rejected = await client.post(
        f"{REQUESTS_URL}/{request['id']}/reject", json={"comment": "Please add a quote"}, headers=manager
    )
    edited = await client.patch(f"{REQUESTS_URL}/{request['id']}", json={"notes": "Quote attached"}, headers=employee)
    resubmitted = await client.post(f"{REQUESTS_URL}/{request['id']}/submit", headers=employee)
    steps = await approval_steps(client, employee, "purchase_request", request["id"])

    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["rejection_reason"] == "Please add a quote"
    assert edited.status_code == 200
    assert resubmitted.json()["status"] == "submitted"
    assert resubmitted.json()["rejection_reason"] is None
    assert [(step["round"], step["status"]) for step in steps] == [(1, "rejected"), (2, "pending")]


async def test_a_rejection_needs_a_reason(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    employee = await auth_headers("employee")
    manager = await auth_headers("department_manager")
    request = await _submitted(client, employee)

    response = await client.post(f"{REQUESTS_URL}/{request['id']}/reject", json={"comment": ""}, headers=manager)

    assert response.status_code == 422


async def test_the_owner_can_cancel_and_the_waiting_step_is_closed(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    employee = await auth_headers("employee")
    manager = await auth_headers("department_manager")
    request = await _submitted(client, employee)

    cancelled = await client.post(f"{REQUESTS_URL}/{request['id']}/cancel", headers=employee)
    approve_after = await client.post(f"{REQUESTS_URL}/{request['id']}/approve", headers=manager)
    steps = await approval_steps(client, employee, "purchase_request", request["id"])

    assert cancelled.json()["status"] == "cancelled"
    assert approve_after.status_code == 409
    assert [step["status"] for step in steps] == ["skipped"]
    assert (await queue(client, manager))["total"] == 0


async def test_an_approved_request_cannot_be_cancelled_or_resubmitted(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    employee = await auth_headers("employee")
    manager = await auth_headers("department_manager")
    request = await _approved(client, employee, manager)

    cancel = await client.post(f"{REQUESTS_URL}/{request['id']}/cancel", headers=employee)
    submit = await client.post(f"{REQUESTS_URL}/{request['id']}/submit", headers=employee)

    assert cancel.status_code == 409
    assert submit.status_code == 409


async def test_a_delegate_can_open_and_decide_a_request_they_were_delegated(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    employee = await auth_headers("employee")
    manager = await auth_headers("department_manager")
    stand_in = await auth_headers("warehouse_manager")
    today = utc_today()
    await client.post(
        f"{API}/approval-delegations",
        json={
            "delegate_id": await user_id(client, stand_in),
            "starts_on": today.isoformat(),
            "ends_on": (today + timedelta(days=2)).isoformat(),
        },
        headers=manager,
    )
    request = await _submitted(client, employee)

    seen = await client.get(f"{REQUESTS_URL}/{request['id']}", headers=stand_in)
    decided = await client.post(f"{REQUESTS_URL}/{request['id']}/approve", headers=stand_in)

    assert seen.status_code == 200
    assert decided.status_code == 200


# --- conversion into purchase orders ---------------------------------------------------------------------------


async def test_an_approved_request_becomes_one_draft_order_per_supplier(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    db_session: AsyncSession,
    supplier: Supplier,
    product: Product,
) -> None:
    other_supplier = Supplier(name="Second Supplier", email="second@example.com")
    other_product = Product(sku="TEST-002", name="Second Widget", cost=5, minimum_stock=1, supplier_id=supplier.id)
    db_session.add_all([other_supplier, other_product])
    await db_session.commit()
    employee = await auth_headers("employee")
    manager = await auth_headers("department_manager")
    officer = await auth_headers("purchasing_officer")
    request = await _approved(
        client,
        employee,
        manager,
        lines=[
            {"description": "Widgets", "quantity": 4, "estimated_unit_price": "10.00", "product_id": product.id},
            {"description": "Bits", "quantity": 2, "estimated_unit_price": "5.50", "product_id": other_product.id},
        ],
    )
    first, second = request["lines"]

    response = await client.post(
        f"{REQUESTS_URL}/{request['id']}/convert",
        json={
            "orders": [
                {"supplier_id": supplier.id, "lines": [{"line_id": first["id"]}]},
                {"supplier_id": other_supplier.id, "lines": [{"line_id": second["id"], "unit_price": "5.25"}]},
            ]
        },
        headers=officer,
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["purchase_order_ids"]) == 2
    assert body["request"]["status"] == "converted"
    assert {line["converted_po_id"] for line in body["request"]["lines"]} == set(body["purchase_order_ids"])
    orders = [
        (await client.get(f"{API}/purchase-orders/{po_id}", headers=officer)).json()
        for po_id in body["purchase_order_ids"]
    ]
    assert [order["status"] for order in orders] == ["draft", "draft"]
    assert [order["grand_total"] for order in orders] == ["40.00", "10.50"]
    assert all(order["purchase_request_id"] == request["id"] for order in orders)
    assert all(order["currency_code"] == "USD" for order in orders)


async def test_a_line_can_only_be_ordered_once_and_the_request_stays_approved_until_all_are(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    employee = await auth_headers("employee")
    manager = await auth_headers("department_manager")
    officer = await auth_headers("purchasing_officer")
    request = await _approved(
        client,
        employee,
        manager,
        lines=[
            {"description": "Widgets", "quantity": 1, "estimated_unit_price": "10.00", "product_id": product.id},
            {"description": "Consulting day", "quantity": 1, "estimated_unit_price": "800.00"},
        ],
    )
    widgets, consulting = request["lines"]
    url = f"{REQUESTS_URL}/{request['id']}/convert"

    partial = await client.post(
        url, json={"orders": [{"supplier_id": supplier.id, "lines": [{"line_id": widgets["id"]}]}]}, headers=officer
    )
    again = await client.post(
        url, json={"orders": [{"supplier_id": supplier.id, "lines": [{"line_id": widgets["id"]}]}]}, headers=officer
    )
    unmapped = await client.post(
        url, json={"orders": [{"supplier_id": supplier.id, "lines": [{"line_id": consulting["id"]}]}]}, headers=officer
    )
    mapped = await client.post(
        url,
        json={
            "orders": [{"supplier_id": supplier.id, "lines": [{"line_id": consulting["id"], "product_id": product.id}]}]
        },
        headers=officer,
    )

    assert partial.json()["request"]["status"] == "approved"
    assert again.status_code == 409
    assert unmapped.status_code == 422
    assert "choose one" in unmapped.json()["detail"]
    assert mapped.status_code == 200
    assert mapped.json()["request"]["status"] == "converted"


async def test_conversion_is_refused_for_the_wrong_state_the_wrong_person_and_bad_lines(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    employee = await auth_headers("employee")
    manager = await auth_headers("department_manager")
    officer = await auth_headers("purchasing_officer")
    draft = (await _create(client, employee, lines=[{**LINE, "product_id": product.id}])).json()
    approved = await _approved(client, employee, manager, lines=[{**LINE, "product_id": product.id}])
    line_id = approved["lines"][0]["id"]
    body = {"orders": [{"supplier_id": supplier.id, "lines": [{"line_id": line_id}]}]}

    not_approved = await client.post(f"{REQUESTS_URL}/{draft['id']}/convert", json=body, headers=officer)
    by_employee = await client.post(f"{REQUESTS_URL}/{approved['id']}/convert", json=body, headers=employee)
    foreign_line = await client.post(
        f"{REQUESTS_URL}/{approved['id']}/convert",
        json={"orders": [{"supplier_id": supplier.id, "lines": [{"line_id": 99999}]}]},
        headers=officer,
    )
    bad_supplier = await client.post(
        f"{REQUESTS_URL}/{approved['id']}/convert",
        json={"orders": [{"supplier_id": 99999, "lines": [{"line_id": line_id}]}]},
        headers=officer,
    )
    twice_in_one_call = await client.post(
        f"{REQUESTS_URL}/{approved['id']}/convert",
        json={"orders": [{"supplier_id": supplier.id, "lines": [{"line_id": line_id}]}] * 2},
        headers=officer,
    )

    assert not_approved.status_code == 409
    assert by_employee.status_code == 403
    assert foreign_line.status_code == 400
    assert bad_supplier.status_code == 400
    assert twice_in_one_call.status_code == 409
    # Nothing was created by the refused attempts.
    assert (await client.get(f"{REQUESTS_URL}/{approved['id']}", headers=officer)).json()["status"] == "approved"
