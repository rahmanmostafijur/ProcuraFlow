from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_today
from app.models.enums import POStatus
from app.models.notification import Notification
from app.models.product import Product
from app.models.supplier import Supplier
from tests.fixture_types import AuthHeaders, MakeUser
from tests.flow_helpers import API, approve_po, get_po, submitted_po, user_id
from tests.po_factory import build_po

CENTRES_URL = f"{API}/cost-centres"
BUDGETS_URL = f"{API}/budgets"
TRANSFERS_URL = f"{API}/budget-transfers"
FISCAL_YEAR = utc_today().year


async def _centre(client: AsyncClient, headers: dict[str, str], code: str = "MKT", **extra: Any) -> dict[str, Any]:
    response = await client.post(CENTRES_URL, json={"code": code, "name": f"{code} team", **extra}, headers=headers)
    assert response.status_code == 201, response.text
    return dict(response.json())


async def _budget(
    client: AsyncClient,
    headers: dict[str, str],
    cost_centre_id: int,
    amount: str,
    *,
    fiscal_year: int = FISCAL_YEAR,
    reason: str | None = None,
) -> Response:
    return await client.put(
        BUDGETS_URL,
        json={"cost_centre_id": cost_centre_id, "fiscal_year": fiscal_year, "amount": amount, "reason": reason},
        headers=headers,
    )


async def _settings(client: AsyncClient, admin: dict[str, str], **changes: Any) -> None:
    response = await client.patch(f"{API}/company-settings", json=changes, headers=admin)
    assert response.status_code == 200, response.text


# --- cost centres ----------------------------------------------------------------------------------------------


async def test_finance_creates_and_edits_cost_centres_and_anyone_can_list_them(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    finance = await auth_headers("finance")
    employee = await auth_headers("employee")
    manager = await auth_headers("department_manager")

    created = await _centre(client, finance, "ops", manager_id=await user_id(client, manager))
    renamed = await client.patch(f"{CENTRES_URL}/{created['id']}", json={"name": "Operations"}, headers=finance)
    retired = await client.patch(f"{CENTRES_URL}/{created['id']}", json={"is_active": False}, headers=finance)
    everyone = await client.get(CENTRES_URL, headers=employee)
    active = await client.get(CENTRES_URL, params={"active_only": True}, headers=employee)

    assert created["code"] == "OPS"
    assert renamed.json()["name"] == "Operations"
    assert retired.json()["is_active"] is False
    assert [row["code"] for row in everyone.json()] == ["OPS"]
    assert active.json() == []


async def test_cost_centre_codes_are_unique_and_managers_must_exist(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    finance = await auth_headers("finance")
    await _centre(client, finance, "MKT")

    duplicate = await client.post(CENTRES_URL, json={"code": "mkt", "name": "Again"}, headers=finance)
    ghost_manager = await client.post(
        CENTRES_URL, json={"code": "HR", "name": "People", "manager_id": 99999}, headers=finance
    )

    assert duplicate.status_code == 409
    assert ghost_manager.status_code == 400


@pytest.mark.parametrize("role", ["viewer", "employee", "procurement_manager", "department_manager"])
async def test_only_budget_managers_can_change_cost_centres_budgets_and_decide_transfers(
    client: AsyncClient, auth_headers: AuthHeaders, role: str
) -> None:
    finance = await auth_headers("finance")
    centre = await _centre(client, finance)
    headers = await auth_headers(role)

    results = [
        await client.post(CENTRES_URL, json={"code": "X", "name": "X"}, headers=headers),
        await client.patch(f"{CENTRES_URL}/{centre['id']}", json={"name": "Hijacked"}, headers=headers),
        await _budget(client, headers, centre["id"], "100"),
        await client.post(f"{TRANSFERS_URL}/1/approve", headers=headers),
        await client.post(f"{TRANSFERS_URL}/1/reject", json={"comment": "no"}, headers=headers),
    ]

    assert {result.status_code for result in results} == {403}


async def test_budget_figures_are_hidden_from_roles_without_the_read_permission(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    finance = await auth_headers("finance")
    centre = await _centre(client, finance)
    await _budget(client, finance, centre["id"], "100")
    employee = await auth_headers("employee")

    listed = await client.get(BUDGETS_URL, headers=employee)
    history = await client.get(f"{BUDGETS_URL}/1/history", headers=employee)

    assert listed.status_code == 403
    assert history.status_code == 403


async def test_budget_and_cost_centre_endpoints_require_sign_in(client: AsyncClient) -> None:
    for url in (CENTRES_URL, BUDGETS_URL, TRANSFERS_URL):
        assert (await client.get(url)).status_code == 401


# --- budgets and their history ----------------------------------------------------------------------------------


async def test_a_budget_starts_empty_of_spend_and_every_change_is_recorded(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    finance = await auth_headers("finance")
    centre = await _centre(client, finance)

    created = await _budget(client, finance, centre["id"], "10000", reason="Annual plan")
    unchanged = await _budget(client, finance, centre["id"], "10000")
    adjusted = await _budget(client, finance, centre["id"], "12000", reason="Extra campaign")
    listed = await client.get(BUDGETS_URL, headers=finance)
    budget_id = listed.json()[0]["budget_id"]
    history = await client.get(f"{BUDGETS_URL}/{budget_id}/history", headers=finance)

    assert created.json()["budget"] == "10000.00"
    assert (created.json()["spent"], created.json()["committed"], created.json()["remaining"]) == (
        "0.00",
        "0.00",
        "10000.00",
    )
    assert created.json()["health"] == "ok"
    assert unchanged.status_code == 200
    assert adjusted.json()["budget"] == "12000.00"
    assert [(row["change_type"], row["old_amount"], row["new_amount"], row["reason"]) for row in history.json()] == [
        ("adjusted", "10000.00", "12000.00", "Extra campaign"),
        ("created", None, "10000.00", "Annual plan"),
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {"amount": "-1"},
        {"amount": "1.123456"},
        {"fiscal_year": 1999},
        {"fiscal_year": 2101},
        {"cost_centre_id": 99999},
    ],
)
async def test_invalid_budgets_are_rejected(
    client: AsyncClient, auth_headers: AuthHeaders, payload: dict[str, Any]
) -> None:
    finance = await auth_headers("finance")
    centre = await _centre(client, finance)
    body: dict[str, Any] = {"cost_centre_id": centre["id"], "fiscal_year": FISCAL_YEAR, "amount": "100", **payload}

    response = await client.put(BUDGETS_URL, json=body, headers=finance)

    assert response.status_code in {400, 422}


async def test_an_inactive_cost_centre_cannot_get_a_budget(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    finance = await auth_headers("finance")
    centre = await _centre(client, finance)
    await client.patch(f"{CENTRES_URL}/{centre['id']}", json={"is_active": False}, headers=finance)

    response = await _budget(client, finance, centre["id"], "100")

    assert response.status_code == 400


async def test_history_of_an_unknown_budget_is_404(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    finance = await auth_headers("finance")

    assert (await client.get(f"{BUDGETS_URL}/99999/history", headers=finance)).status_code == 404


# --- spent, committed, remaining -------------------------------------------------------------------------------


async def _seed_orders(db: AsyncSession, creator_id: int, supplier: Supplier, product: Product, centre_id: int) -> None:
    now = datetime.now(UTC)
    last_year = datetime(FISCAL_YEAR - 1, 6, 15, tzinfo=UTC)
    # price x quantity: received 300, approved 100 and ordered 50 are this year's; drafts, cancelled and last
    # year's orders must never count.
    orders = [
        ("PO-B-1", POStatus.RECEIVED, "300.00", now),
        ("PO-B-2", POStatus.APPROVED, "100.00", now),
        ("PO-B-3", POStatus.ORDERED, "50.00", now),
        ("PO-B-4", POStatus.DRAFT, "9999.00", now),
        ("PO-B-5", POStatus.CANCELLED, "9999.00", now),
        ("PO-B-6", POStatus.RECEIVED, "7777.00", last_year),
    ]
    for number, status, price, approved_at in orders:
        db.add(
            build_po(
                po_number=number,
                supplier_id=supplier.id,
                created_by=creator_id,
                status=status,
                lines=[(product.id, 1, Decimal(price))],
                cost_centre_id=centre_id,
                approved_at=approved_at,
            )
        )
    await db.commit()


async def test_positions_split_spent_from_committed_and_ignore_other_years_and_open_orders(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    make_user: MakeUser,
    db_session: AsyncSession,
    supplier: Supplier,
    product: Product,
) -> None:
    finance = await auth_headers("finance")
    centre = await _centre(client, finance)
    other = await _centre(client, finance, "OPS")
    await _budget(client, finance, centre["id"], "1000")
    await _budget(client, finance, other["id"], "500")
    creator = await make_user("creator@example.com", "procurement_manager")
    await _seed_orders(db_session, creator.id, supplier, product, centre["id"])

    response = await client.get(BUDGETS_URL, headers=finance)

    by_code = {row["cost_centre_code"]: row for row in response.json()}
    marketing = by_code["MKT"]
    assert (marketing["budget"], marketing["spent"], marketing["committed"], marketing["remaining"]) == (
        "1000.00",
        "300.00",
        "150.00",
        "550.00",
    )
    assert Decimal(marketing["utilisation_percent"]) == Decimal("45.0")
    assert marketing["health"] == "ok"
    assert by_code["OPS"]["spent"] == "0.00"
    assert by_code["OPS"]["remaining"] == "500.00"


async def test_a_previous_fiscal_year_is_reported_on_its_own(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    make_user: MakeUser,
    db_session: AsyncSession,
    supplier: Supplier,
    product: Product,
) -> None:
    finance = await auth_headers("finance")
    centre = await _centre(client, finance)
    await _budget(client, finance, centre["id"], "9000", fiscal_year=FISCAL_YEAR - 1)
    creator = await make_user("creator@example.com", "procurement_manager")
    await _seed_orders(db_session, creator.id, supplier, product, centre["id"])

    response = await client.get(BUDGETS_URL, params={"fiscal_year": FISCAL_YEAR - 1}, headers=finance)

    [row] = response.json()
    assert (row["spent"], row["committed"], row["remaining"]) == ("7777.00", "0.00", "1223.00")


async def test_the_fiscal_year_follows_the_company_setting(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    make_user: MakeUser,
    db_session: AsyncSession,
    supplier: Supplier,
    product: Product,
) -> None:
    admin = await auth_headers("admin")
    finance = await auth_headers("finance")
    centre = await _centre(client, finance)
    creator = await make_user("creator@example.com", "procurement_manager")
    db_session.add(
        build_po(
            po_number="PO-FY-1",
            supplier_id=supplier.id,
            created_by=creator.id,
            status=POStatus.APPROVED,
            lines=[(product.id, 1, Decimal("200.00"))],
            cost_centre_id=centre["id"],
            approved_at=datetime(2026, 3, 31, 12, 0, tzinfo=UTC),
        )
    )
    await db_session.commit()
    await _settings(client, admin, fiscal_year_start_month=4)
    await _budget(client, finance, centre["id"], "1000", fiscal_year=2025)
    await _budget(client, finance, centre["id"], "1000", fiscal_year=2026)

    in_2025 = await client.get(BUDGETS_URL, params={"fiscal_year": 2025}, headers=finance)
    in_2026 = await client.get(BUDGETS_URL, params={"fiscal_year": 2026}, headers=finance)

    # With an April start, 31 March 2026 is the last day of fiscal year 2025.
    assert in_2025.json()[0]["committed"] == "200.00"
    assert in_2026.json()[0]["committed"] == "0.00"


async def test_health_warns_at_the_configured_share_and_flags_overspend(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    make_user: MakeUser,
    db_session: AsyncSession,
    supplier: Supplier,
    product: Product,
) -> None:
    admin = await auth_headers("admin")
    finance = await auth_headers("finance")
    creator = await make_user("creator@example.com", "procurement_manager")
    await _settings(client, admin, budget_warn_percent="70")
    near = await _centre(client, finance, "NEAR")
    over = await _centre(client, finance, "OVER")
    quiet = await _centre(client, finance, "QUIET")
    for centre, amount, spend in ((near, "1000", "700.00"), (over, "1000", "1200.00"), (quiet, "1000", "100.00")):
        await _budget(client, finance, centre["id"], amount)
        db_session.add(
            build_po(
                po_number=f"PO-H-{centre['code']}",
                supplier_id=supplier.id,
                created_by=creator.id,
                status=POStatus.APPROVED,
                lines=[(product.id, 1, Decimal(spend))],
                cost_centre_id=centre["id"],
                approved_at=datetime.now(UTC),
            )
        )
    await db_session.commit()

    rows = {row["cost_centre_code"]: row for row in (await client.get(BUDGETS_URL, headers=finance)).json()}

    assert rows["QUIET"]["health"] == "ok"
    assert rows["NEAR"]["health"] == "warning"
    assert rows["OVER"]["health"] == "over"
    assert rows["OVER"]["remaining"] == "-200.00"


async def test_the_budget_settings_are_validated(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    admin = await auth_headers("admin")

    over = await client.patch(f"{API}/company-settings", json={"budget_warn_percent": "100.5"}, headers=admin)
    negative = await client.patch(f"{API}/company-settings", json={"budget_warn_percent": "-1"}, headers=admin)
    cleared = await client.patch(f"{API}/company-settings", json={"budget_block_over_budget": None}, headers=admin)

    assert {over.status_code, negative.status_code, cleared.status_code} == {422}


# --- the rules applied to approvals ----------------------------------------------------------------------------


async def test_an_order_that_would_break_a_blocking_budget_cannot_be_approved(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    admin = await auth_headers("admin")
    finance = await auth_headers("finance")
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    centre = await _centre(client, finance)
    await _budget(client, finance, centre["id"], "100")
    await _settings(client, admin, budget_block_over_budget=True)
    po = await submitted_po(
        client, officer, supplier, product, quantity=50, unit_price="10.00", cost_centre_id=centre["id"]
    )

    response = await approve_po(client, manager, po["id"])

    assert response.status_code == 409
    assert "over its" in response.json()["detail"]
    assert f"FY{FISCAL_YEAR}" in response.json()["detail"]
    assert "100.00 USD is left and this needs 500.00" in response.json()["detail"]
    assert (await get_po(client, manager, po["id"]))["status"] == "submitted"


async def test_the_budget_check_counts_what_is_already_committed(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    admin = await auth_headers("admin")
    finance = await auth_headers("finance")
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    centre = await _centre(client, finance)
    await _budget(client, finance, centre["id"], "100")
    await _settings(client, admin, budget_block_over_budget=True)
    first = await submitted_po(
        client, officer, supplier, product, quantity=8, unit_price="10.00", cost_centre_id=centre["id"]
    )
    second = await submitted_po(
        client, officer, supplier, product, quantity=3, unit_price="10.00", cost_centre_id=centre["id"]
    )

    approved_first = await approve_po(client, manager, first["id"])
    refused_second = await approve_po(client, manager, second["id"])

    assert approved_first.status_code == 200
    assert refused_second.status_code == 409
    assert "20.00 USD is left and this needs 30.00" in refused_second.json()["detail"]


async def test_the_same_order_is_approved_when_the_company_does_not_block_overspend(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    finance = await auth_headers("finance")
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    centre = await _centre(client, finance)
    await _budget(client, finance, centre["id"], "100")
    po = await submitted_po(
        client, officer, supplier, product, quantity=50, unit_price="10.00", cost_centre_id=centre["id"]
    )

    response = await approve_po(client, manager, po["id"])

    assert response.status_code == 200


async def test_a_cost_centre_without_a_budget_for_the_year_is_not_limited(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    admin = await auth_headers("admin")
    finance = await auth_headers("finance")
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    centre = await _centre(client, finance)
    await _budget(client, finance, centre["id"], "10", fiscal_year=FISCAL_YEAR + 1)
    await _settings(client, admin, budget_block_over_budget=True)
    po = await submitted_po(
        client, officer, supplier, product, quantity=50, unit_price="10.00", cost_centre_id=centre["id"]
    )

    assert (await approve_po(client, manager, po["id"])).status_code == 200


async def test_an_order_without_a_cost_centre_is_never_limited(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    admin = await auth_headers("admin")
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    await _settings(client, admin, budget_block_over_budget=True)
    po = await submitted_po(client, officer, supplier, product)

    assert (await approve_po(client, manager, po["id"])).status_code == 200


async def test_a_request_that_would_break_a_blocking_budget_cannot_be_approved(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    admin = await auth_headers("admin")
    finance = await auth_headers("finance")
    employee = await auth_headers("employee")
    manager = await auth_headers("department_manager")
    centre = await _centre(client, finance)
    await _budget(client, finance, centre["id"], "100")
    await _settings(client, admin, budget_block_over_budget=True)
    request = (
        await client.post(
            f"{API}/purchase-requests",
            json={
                "title": "Too much",
                "cost_centre_id": centre["id"],
                "lines": [{"description": "Stuff", "quantity": 1, "estimated_unit_price": "500.00"}],
            },
            headers=employee,
        )
    ).json()
    await client.post(f"{API}/purchase-requests/{request['id']}/submit", headers=employee)

    response = await client.post(f"{API}/purchase-requests/{request['id']}/approve", headers=manager)

    assert response.status_code == 409
    assert "over its" in response.json()["detail"]
    assert (await client.get(f"{API}/purchase-requests/{request['id']}", headers=employee)).json()[
        "status"
    ] == "submitted"


async def test_approving_past_the_warning_level_notifies_the_owner_and_the_cost_centre_manager(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession, supplier: Supplier, product: Product
) -> None:
    finance = await auth_headers("finance")
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    head = await auth_headers("department_manager")
    centre = await _centre(client, finance, manager_id=await user_id(client, head))
    await _budget(client, finance, centre["id"], "100")
    po = await submitted_po(
        client, officer, supplier, product, quantity=9, unit_price="10.00", cost_centre_id=centre["id"]
    )

    await approve_po(client, manager, po["id"])

    notes = (await db_session.scalars(select(Notification))).all()
    assert {note.user_id for note in notes} == {await user_id(client, officer), await user_id(client, head)}
    assert all("90%" in note.message and "MKT team" in note.message for note in notes)


async def test_a_small_order_well_inside_the_budget_sends_no_warning(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession, supplier: Supplier, product: Product
) -> None:
    finance = await auth_headers("finance")
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    centre = await _centre(client, finance)
    await _budget(client, finance, centre["id"], "10000")
    po = await submitted_po(
        client, officer, supplier, product, quantity=1, unit_price="10.00", cost_centre_id=centre["id"]
    )

    await approve_po(client, manager, po["id"])

    assert (await db_session.scalars(select(Notification))).all() == []


async def test_orders_and_requests_need_an_active_cost_centre(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    officer = await auth_headers("purchasing_officer")

    response = await client.post(
        f"{API}/purchase-orders",
        json={
            "supplier_id": supplier.id,
            "cost_centre_id": 99999,
            "items": [{"product_id": product.id, "quantity": 1, "unit_price": "1"}],
        },
        headers=officer,
    )

    assert response.status_code == 400


# --- transfers ---------------------------------------------------------------------------------------------------


async def _two_budgets(client: AsyncClient, finance: dict[str, str]) -> tuple[int, int]:
    first = await _budget(client, finance, (await _centre(client, finance, "MKT"))["id"], "1000")
    second = await _budget(client, finance, (await _centre(client, finance, "OPS"))["id"], "500")
    return first.json()["budget_id"], second.json()["budget_id"]


async def _transfer(
    client: AsyncClient, headers: dict[str, str], source: int, target: int, amount: str = "200"
) -> Response:
    return await client.post(
        TRANSFERS_URL,
        json={"from_budget_id": source, "to_budget_id": target, "amount": amount, "reason": "Rebalancing for Q4"},
        headers=headers,
    )


async def test_a_transfer_takes_effect_only_when_finance_approves_it_and_both_budgets_record_it(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    finance = await auth_headers("finance")
    head = await auth_headers("department_manager")
    source, target = await _two_budgets(client, finance)

    requested = await _transfer(client, head, source, target)
    untouched = {row["budget_id"]: row["budget"] for row in (await client.get(BUDGETS_URL, headers=finance)).json()}
    approved = await client.post(
        f"{TRANSFERS_URL}/{requested.json()['id']}/approve", json={"comment": "OK"}, headers=finance
    )
    moved = {row["budget_id"]: row["budget"] for row in (await client.get(BUDGETS_URL, headers=finance)).json()}
    source_history = await client.get(f"{BUDGETS_URL}/{source}/history", headers=finance)
    target_history = await client.get(f"{BUDGETS_URL}/{target}/history", headers=finance)

    assert requested.status_code == 201
    assert requested.json()["status"] == "pending"
    assert (requested.json()["from_label"], requested.json()["to_label"]) == (
        f"MKT FY{FISCAL_YEAR}",
        f"OPS FY{FISCAL_YEAR}",
    )
    assert untouched == {source: "1000.00", target: "500.00"}
    assert approved.json()["status"] == "approved"
    assert approved.json()["decided_by"]["full_name"] == "Finance User"
    assert moved == {source: "800.00", target: "700.00"}
    assert (source_history.json()[0]["change_type"], source_history.json()[0]["new_amount"]) == (
        "transfer_out",
        "800.00",
    )
    assert (target_history.json()[0]["change_type"], target_history.json()[0]["new_amount"]) == (
        "transfer_in",
        "700.00",
    )
    assert source_history.json()[0]["transfer_id"] == requested.json()["id"]


async def test_nobody_decides_a_transfer_they_requested(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    finance = await auth_headers("finance")
    admin = await auth_headers("admin")
    source, target = await _two_budgets(client, finance)
    transfer = (await _transfer(client, admin, source, target)).json()

    response = await client.post(f"{TRANSFERS_URL}/{transfer['id']}/approve", headers=admin)

    assert response.status_code == 403
    assert "you requested" in response.json()["detail"]


async def test_a_rejected_transfer_changes_nothing_and_needs_a_reason(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    finance = await auth_headers("finance")
    head = await auth_headers("department_manager")
    source, target = await _two_budgets(client, finance)
    transfer = (await _transfer(client, head, source, target)).json()

    without_reason = await client.post(f"{TRANSFERS_URL}/{transfer['id']}/reject", headers=finance)
    rejected = await client.post(
        f"{TRANSFERS_URL}/{transfer['id']}/reject", json={"comment": "Not this quarter"}, headers=finance
    )
    decided_again = await client.post(f"{TRANSFERS_URL}/{transfer['id']}/approve", headers=finance)
    amounts = {row["budget_id"]: row["budget"] for row in (await client.get(BUDGETS_URL, headers=finance)).json()}

    assert without_reason.status_code == 422
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["decision_comment"] == "Not this quarter"
    assert decided_again.status_code == 409
    assert amounts == {source: "1000.00", target: "500.00"}


async def test_only_unspent_budget_can_be_moved(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    make_user: MakeUser,
    db_session: AsyncSession,
    supplier: Supplier,
    product: Product,
) -> None:
    finance = await auth_headers("finance")
    head = await auth_headers("department_manager")
    source, target = await _two_budgets(client, finance)
    centre_id = (await client.get(BUDGETS_URL, headers=finance)).json()[0]["cost_centre_id"]
    creator = await make_user("creator@example.com", "procurement_manager")
    db_session.add(
        build_po(
            po_number="PO-T-1",
            supplier_id=supplier.id,
            created_by=creator.id,
            status=POStatus.ORDERED,
            lines=[(product.id, 1, Decimal("900.00"))],
            cost_centre_id=centre_id,
            approved_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    refused = await _transfer(client, head, source, target, amount="200")
    allowed = await _transfer(client, head, source, target, amount="100")

    assert refused.status_code == 409
    assert "unspent and uncommitted" in refused.json()["detail"]
    assert allowed.status_code == 201


async def test_transfers_are_validated(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    finance = await auth_headers("finance")
    head = await auth_headers("department_manager")
    source, target = await _two_budgets(client, finance)
    other_year = (
        await _budget(
            client,
            finance,
            (await client.get(CENTRES_URL, headers=finance)).json()[0]["id"],
            "100",
            fiscal_year=FISCAL_YEAR + 1,
        )
    ).json()["budget_id"]

    same = await _transfer(client, head, source, source)
    zero = await _transfer(client, head, source, target, amount="0")
    ghost = await _transfer(client, head, source, 99999)
    cross_year = await _transfer(client, head, source, other_year)
    no_reason = await client.post(
        TRANSFERS_URL,
        json={"from_budget_id": source, "to_budget_id": target, "amount": "5", "reason": ""},
        headers=head,
    )

    assert same.status_code == 422
    assert zero.status_code == 422
    assert ghost.status_code == 404
    assert cross_year.status_code == 422
    assert no_reason.status_code == 422


async def test_a_role_without_the_transfer_permission_cannot_ask(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    finance = await auth_headers("finance")
    source, target = await _two_budgets(client, finance)
    employee = await auth_headers("employee")

    assert (await _transfer(client, employee, source, target)).status_code == 403
    assert (await _transfer(client, finance, source, target)).status_code == 403


async def test_people_see_only_their_own_transfers_unless_they_manage_budgets(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    finance = await auth_headers("finance")
    head = await auth_headers("department_manager", email="head1@example.com")
    other_head = await auth_headers("department_manager", email="head2@example.com")
    source, target = await _two_budgets(client, finance)
    transfer = (await _transfer(client, head, source, target)).json()

    mine = await client.get(TRANSFERS_URL, headers=head)
    others = await client.get(TRANSFERS_URL, headers=other_head)
    finance_list = await client.get(TRANSFERS_URL, headers=finance)
    own_detail = await client.get(f"{TRANSFERS_URL}/{transfer['id']}", headers=head)
    other_detail = await client.get(f"{TRANSFERS_URL}/{transfer['id']}", headers=other_head)

    assert [row["id"] for row in mine.json()] == [transfer["id"]]
    assert others.json() == []
    assert [row["id"] for row in finance_list.json()] == [transfer["id"]]
    assert own_detail.status_code == 200
    assert other_detail.status_code == 404
