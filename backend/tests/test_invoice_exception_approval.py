from datetime import timedelta
from typing import Any

from httpx import AsyncClient

from app.core.clock import utc_today
from app.models.product import Product
from app.models.supplier import Supplier
from tests.flow_helpers import API, add_rule, approval_steps, queue, set_limit, user_id
from tests.invoice_helpers import (
    INVOICES,
    Staff,
    add_rate,
    create_invoice,
    delete_all_rates,
    get_invoice,
    invoice_body,
    received_po,
    submit_invoice,
)

DOCUMENT = "invoice_exception"
# Ten units at 20.00 against an order priced 10.00: a price variance and a total over the order.
EXCEPTION_PRICE = "20.00"


async def _exception(
    client: AsyncClient,
    staff: Staff,
    supplier: Supplier,
    product: Product,
    *,
    creator: dict[str, str] | None = None,
    po: dict[str, Any] | None = None,
) -> dict[str, Any]:
    creator = creator or staff.officer
    po = po or await received_po(client, staff, supplier, product)
    invoice = await create_invoice(client, creator, invoice_body(po, product, unit_price=EXCEPTION_PRICE))
    response = await submit_invoice(client, creator, invoice["id"])
    assert response.json()["status"] == "exception", response.text
    return dict(response.json())


async def _approve(client: AsyncClient, headers: dict[str, str], invoice_id: int, **body: Any) -> Any:
    return await client.post(f"{INVOICES}/{invoice_id}/approve", json=body or None, headers=headers)


async def _reject(client: AsyncClient, headers: dict[str, str], invoice_id: int, comment: str = "Not right") -> Any:
    return await client.post(f"{INVOICES}/{invoice_id}/reject", json={"comment": comment}, headers=headers)


async def test_an_exception_opens_one_step_for_anyone_with_the_approve_permission_when_no_rule_applies(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    invoice = await _exception(client, staff, supplier, product)

    steps = await approval_steps(client, staff.finance, DOCUMENT, invoice["id"])
    approved = await _approve(client, staff.finance, invoice["id"], comment="Agreed price rise")

    assert [(step["required_permission"], step["status"]) for step in steps] == [("invoice:approve", "pending")]
    assert steps[0]["amount_base"] == "200.00"
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["base_grand_total"] == "200.00"
    final = await approval_steps(client, staff.finance, DOCUMENT, invoice["id"])
    assert final[0]["comment"] == "Agreed price rise"
    assert final[0]["decided_by_person"]["full_name"] == "Finance User"


async def test_someone_without_the_permission_or_role_cannot_decide_an_exception(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    invoice = await _exception(client, staff, supplier, product)

    response = await _approve(client, staff.manager, invoice["id"])

    assert response.status_code == 403
    assert response.json()["detail"] == "You do not have the 'invoice:approve' permission"
    assert (await get_invoice(client, staff.finance, invoice["id"]))["status"] == "exception"


async def test_the_person_who_recorded_an_exception_cannot_approve_it(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    invoice = await _exception(client, staff, supplier, product, creator=staff.finance)

    own = await _approve(client, staff.finance, invoice["id"])
    other = await _approve(client, staff.finance2, invoice["id"])

    assert own.status_code == 403
    assert own.json()["detail"] == "You cannot approve an invoice you created."
    assert other.status_code == 200


async def test_a_two_step_rule_needs_both_roles_in_order(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    await add_rule(client, staff.finance, document_type=DOCUMENT, roles=["procurement_manager", "finance"])
    invoice = await _exception(client, staff, supplier, product)

    wrong_role_first = await _approve(client, staff.finance, invoice["id"])
    first = await _approve(client, staff.manager, invoice["id"])
    middle = await get_invoice(client, staff.finance, invoice["id"])
    second = await _approve(client, staff.finance, invoice["id"])

    assert wrong_role_first.status_code == 403
    assert "procurement manager role" in wrong_role_first.json()["detail"]
    assert first.status_code == 200
    assert first.json()["status"] == "exception"
    assert middle["status"] == "exception"
    assert second.json()["status"] == "approved"
    steps = await approval_steps(client, staff.finance, DOCUMENT, invoice["id"])
    assert [step["status"] for step in steps] == ["approved", "approved"]


async def test_nobody_approves_two_steps_of_the_same_invoice(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    await add_rule(client, staff.finance, document_type=DOCUMENT, roles=["finance", "finance"])
    invoice = await _exception(client, staff, supplier, product)
    await _approve(client, staff.finance2, invoice["id"])

    again = await _approve(client, staff.finance2, invoice["id"])
    other = await _approve(client, staff.finance, invoice["id"])

    assert again.status_code == 403
    assert "already approved an earlier step" in again.json()["detail"]
    assert other.json()["status"] == "approved"


async def test_an_amount_outside_every_rule_falls_back_to_the_single_permission_step(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    await add_rule(
        client, staff.finance, document_type=DOCUMENT, roles=["procurement_manager"], max_amount="100", name="Small"
    )
    invoice = await _exception(client, staff, supplier, product)

    steps = await approval_steps(client, staff.finance, DOCUMENT, invoice["id"])

    assert [(step["rule_name"], step["required_permission"]) for step in steps] == [(None, "invoice:approve")]


async def test_the_rule_is_picked_by_the_invoice_amount_in_the_base_currency(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    await add_rate(client, staff.finance, "EUR", "2")
    await add_rule(
        client, staff.finance, document_type=DOCUMENT, roles=["procurement_manager"], min_amount="300", name="Big"
    )
    po = await received_po(client, staff, supplier, product, currency_code="EUR")

    invoice = await _exception(client, staff, supplier, product, po=po)

    # 10 x 20.00 EUR = 200 EUR = 400 in the base currency, which falls in the rule's band.
    steps = await approval_steps(client, staff.finance, DOCUMENT, invoice["id"])
    assert [(step["rule_name"], step["amount_base"]) for step in steps] == [("Big", "400.00")]


async def test_rejecting_sends_the_invoice_back_to_draft_and_it_can_be_corrected_and_resubmitted(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    invoice = await _exception(client, staff, supplier, product)

    rejected = await _reject(client, staff.finance, invoice["id"], "Price not agreed")
    corrected = await client.patch(
        f"{INVOICES}/{invoice['id']}",
        json={"lines": [{"product_id": product.id, "quantity": 10, "unit_price": "10.00"}]},
        headers=staff.officer,
    )
    resubmitted = await submit_invoice(client, staff.officer, invoice["id"])

    assert rejected.status_code == 200
    assert rejected.json()["status"] == "draft"
    assert rejected.json()["rejection_reason"] == "Price not agreed"
    assert corrected.status_code == 200
    assert resubmitted.json()["status"] == "matched"
    assert resubmitted.json()["rejection_reason"] is None
    steps = await approval_steps(client, staff.finance, DOCUMENT, invoice["id"])
    assert [(step["round"], step["status"]) for step in steps] == [(1, "rejected")]


async def test_a_resubmitted_exception_opens_a_new_round(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    invoice = await _exception(client, staff, supplier, product)
    await _reject(client, staff.finance, invoice["id"])

    resubmitted = await submit_invoice(client, staff.officer, invoice["id"])
    approved = await _approve(client, staff.finance2, invoice["id"])

    assert resubmitted.json()["status"] == "exception"
    assert approved.json()["status"] == "approved"
    steps = await approval_steps(client, staff.finance, DOCUMENT, invoice["id"])
    assert [(step["round"], step["status"]) for step in steps] == [(1, "rejected"), (2, "approved")]


async def test_a_rejection_at_the_second_step_skips_the_rest(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    await add_rule(client, staff.finance, document_type=DOCUMENT, roles=["procurement_manager", "finance", "admin"])
    invoice = await _exception(client, staff, supplier, product)
    await _approve(client, staff.manager, invoice["id"])

    rejected = await _reject(client, staff.finance, invoice["id"], "No")

    assert rejected.json()["status"] == "draft"
    steps = await approval_steps(client, staff.finance, DOCUMENT, invoice["id"])
    assert [step["status"] for step in steps] == ["approved", "rejected", "skipped"]


async def test_a_delegate_decides_on_behalf_of_the_approver_and_both_are_recorded(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, auth_headers: Any
) -> None:
    cover = await auth_headers("department_manager")
    await add_rule(client, staff.finance, document_type=DOCUMENT, roles=["finance"])
    invoice = await _exception(client, staff, supplier, product)
    today = utc_today()
    delegated = await client.post(
        f"{API}/approval-delegations",
        json={
            "delegate_id": await user_id(client, cover),
            "starts_on": (today - timedelta(days=1)).isoformat(),
            "ends_on": (today + timedelta(days=1)).isoformat(),
        },
        headers=staff.finance,
    )

    approved = await _approve(client, cover, invoice["id"])

    assert delegated.status_code == 201
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    [step] = await approval_steps(client, staff.finance, DOCUMENT, invoice["id"])
    assert step["decided_by_person"]["full_name"] == "Department_Manager User"
    assert step["on_behalf_of_person"]["full_name"] == "Finance User"


async def test_someone_without_a_delegation_cannot_open_or_decide_an_exception_they_are_not_part_of(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, auth_headers: Any
) -> None:
    outsider = await auth_headers("department_manager")
    invoice = await _exception(client, staff, supplier, product)

    approve = await _approve(client, outsider, invoice["id"])
    steps = await client.get(f"{API}/approvals/{DOCUMENT}/{invoice['id']}/steps", headers=outsider)

    assert approve.status_code == 404
    assert steps.status_code == 404


async def test_an_approval_limit_caps_what_a_person_may_approve(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    await set_limit(client, staff.finance, await user_id(client, staff.finance2), DOCUMENT, "100")
    invoice = await _exception(client, staff, supplier, product)

    capped = await _approve(client, staff.finance2, invoice["id"])
    uncapped = await _approve(client, staff.finance, invoice["id"])

    assert capped.status_code == 403
    assert "approval limit for invoice exceptions is 100.00" in capped.json()["detail"]
    assert uncapped.status_code == 200


async def test_the_exception_waits_in_the_queue_of_everyone_who_may_decide_it(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    invoice = await _exception(client, staff, supplier, product)

    finance_queue = await queue(client, staff.finance)
    officer_queue = await queue(client, staff.officer)
    manager_queue = await queue(client, staff.manager)
    await _approve(client, staff.finance, invoice["id"])
    after = await queue(client, staff.finance2)

    [item] = finance_queue["items"]
    assert (item["document_type"], item["document_id"], item["po_id"]) == (DOCUMENT, invoice["id"], None)
    assert item["label"] == f"{supplier.name} {invoice['invoice_number']}"
    assert item["amount_base"] == "200.00"
    assert officer_queue["total"] == 0
    assert manager_queue["total"] == 0
    assert after["total"] == 0


async def test_an_invoice_on_hold_cannot_be_decided_and_leaves_the_queue_until_released(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    invoice = await _exception(client, staff, supplier, product)

    await client.post(f"{INVOICES}/{invoice['id']}/hold", json={"reason": "Query"}, headers=staff.finance)
    blocked = await _approve(client, staff.finance2, invoice["id"])
    held_queue = await queue(client, staff.finance2)
    await client.post(f"{INVOICES}/{invoice['id']}/release", headers=staff.finance)
    released_queue = await queue(client, staff.finance2)
    approved = await _approve(client, staff.finance2, invoice["id"])

    assert blocked.status_code == 409
    assert held_queue["total"] == 0
    assert released_queue["total"] == 1
    assert approved.json()["status"] == "approved"


async def test_voiding_an_exception_removes_it_from_the_queue_and_skips_its_steps(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    invoice = await _exception(client, staff, supplier, product)

    await client.post(f"{INVOICES}/{invoice['id']}/void", json={"reason": "Wrong supplier"}, headers=staff.officer)

    assert (await queue(client, staff.finance))["total"] == 0
    steps = await approval_steps(client, staff.finance, DOCUMENT, invoice["id"])
    assert [step["status"] for step in steps] == ["skipped"]


async def test_approval_locks_the_exchange_rate_and_later_rates_never_move_the_base_amount(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    await add_rate(client, staff.finance, "EUR", "1.1", days_ago=3)
    po = await received_po(client, staff, supplier, product, currency_code="EUR")
    invoice = await create_invoice(client, staff.officer, invoice_body(po, product))
    await submit_invoice(client, staff.officer, invoice["id"])

    approved = await _approve(client, staff.finance, invoice["id"])
    await add_rate(client, staff.finance, "EUR", "9")
    later = await get_invoice(client, staff.finance, invoice["id"])

    assert approved.json()["exchange_rate"] == "1.10000000"
    assert approved.json()["base_grand_total"] == "110.00"
    assert later["base_grand_total"] == "110.00"
    assert later["exchange_rate"] == "1.10000000"


async def test_a_missing_rate_blocks_approval_and_leaves_the_invoice_as_it_was(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    await add_rate(client, staff.finance, "EUR", "1.1")
    po = await received_po(client, staff, supplier, product, currency_code="EUR")
    invoice = await create_invoice(client, staff.officer, invoice_body(po, product))
    await submit_invoice(client, staff.officer, invoice["id"])
    await delete_all_rates(client, staff.finance)

    response = await _approve(client, staff.finance, invoice["id"])

    assert response.status_code == 409
    assert "exchange rate" in response.json()["detail"]
    assert (await get_invoice(client, staff.finance, invoice["id"]))["status"] == "matched"


async def test_a_foreign_exception_cannot_be_submitted_without_a_rate(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    await add_rate(client, staff.finance, "EUR", "1.1")
    po = await received_po(client, staff, supplier, product, currency_code="EUR")
    invoice = await create_invoice(client, staff.officer, invoice_body(po, product, unit_price=EXCEPTION_PRICE))
    await delete_all_rates(client, staff.finance)

    response = await submit_invoice(client, staff.officer, invoice["id"])

    assert response.status_code == 409
    assert "exchange rate" in response.json()["detail"]
    assert (await get_invoice(client, staff.finance, invoice["id"]))["status"] == "draft"


async def test_deciding_an_unknown_invoice_is_not_found(client: AsyncClient, staff: Staff) -> None:
    assert (await _approve(client, staff.finance, 99999)).status_code == 404
    assert (await _reject(client, staff.finance, 99999)).status_code == 404
