from typing import Any

import pytest
from httpx import AsyncClient

from app.core.permissions import PERMISSIONS, ROLE_PERMISSIONS, SUPPLIER_ROLE
from app.models.product import Product
from app.models.supplier import Supplier
from tests.fixture_types import AuthHeaders
from tests.invoice_helpers import (
    INVOICES,
    RETURNS,
    RUNS,
    Staff,
    create_invoice,
    invoice_body,
    received_po,
    submit_invoice,
)

# Supplier accounts are stopped before any permission check (they may only use the portal); they have their own test.
STAFF_ROLE_PERMISSIONS = {role: grants for role, grants in ROLE_PERMISSIONS.items() if role != SUPPLIER_ROLE}
NEW_PERMISSIONS = ("invoice:read", "invoice:write", "invoice:approve", "payment:write", "payment:release")

# method, path, body, the permission the endpoint requires
GUARDED: list[tuple[str, str, dict[str, Any] | None, str]] = [
    ("GET", INVOICES, None, "invoice:read"),
    ("POST", INVOICES, {}, "invoice:write"),
    ("GET", f"{INVOICES}/1", None, "invoice:read"),
    ("PATCH", f"{INVOICES}/1", {}, "invoice:write"),
    ("POST", f"{INVOICES}/1/submit", None, "invoice:write"),
    ("POST", f"{INVOICES}/1/hold", {"reason": "x"}, "invoice:approve"),
    ("POST", f"{INVOICES}/1/release", None, "invoice:approve"),
    ("POST", f"{INVOICES}/1/void", {"reason": "x"}, "invoice:write"),
    ("GET", f"{INVOICES}/1/payments", None, "invoice:read"),
    ("POST", f"{INVOICES}/1/payments", {"amount": "1", "method": "card"}, "payment:write"),
    ("GET", RUNS, None, "invoice:read"),
    ("POST", RUNS, {"invoice_ids": [1]}, "payment:write"),
    ("GET", f"{RUNS}/1", None, "invoice:read"),
    ("POST", f"{RUNS}/1/release", None, "payment:release"),
    ("POST", f"{RUNS}/1/cancel", None, "payment:write"),
    ("POST", RETURNS, {}, "inventory:write"),
    ("POST", f"{RETURNS}/1/status", {"status": "sent"}, "inventory:write"),
]
SIGNED_IN_ONLY: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", RETURNS, None),
    ("GET", f"{RETURNS}/1", None),
    ("POST", f"{INVOICES}/1/approve", None),
    ("POST", f"{INVOICES}/1/reject", {"comment": "x"}),
]


@pytest.mark.parametrize(("method", "path", "body", "permission"), GUARDED)
async def test_every_guarded_endpoint_refuses_roles_without_its_permission(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    method: str,
    path: str,
    body: dict[str, Any] | None,
    permission: str,
) -> None:
    for role, permissions in STAFF_ROLE_PERMISSIONS.items():
        headers = await auth_headers(role)

        response = await client.request(method, path, json=body, headers=headers)

        if permission in permissions:
            # Past the permission check; the record does not exist or the body is empty, so it is not a 403.
            assert response.status_code != 403, f"{role} should reach {method} {path}"
        else:
            assert response.status_code == 403, f"{role} must not reach {method} {path}"
            assert response.json()["detail"] == f"You do not have the '{permission}' permission"


@pytest.mark.parametrize(("method", "path", "body", "permission"), GUARDED)
async def test_a_supplier_account_reaches_none_of_them_and_is_pointed_to_the_portal(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    method: str,
    path: str,
    body: dict[str, Any] | None,
    permission: str,
) -> None:
    response = await client.request(method, path, json=body, headers=await auth_headers(SUPPLIER_ROLE))

    assert response.status_code == 403
    assert response.json()["detail"] == "Supplier accounts can only use the portal"


@pytest.mark.parametrize(("method", "path", "body", "permission"), GUARDED)
async def test_every_guarded_endpoint_needs_sign_in(
    client: AsyncClient, method: str, path: str, body: dict[str, Any] | None, permission: str
) -> None:
    response = await client.request(method, path, json=body)

    assert response.status_code == 401


@pytest.mark.parametrize(("method", "path", "body"), SIGNED_IN_ONLY)
async def test_endpoints_open_to_any_signed_in_user_still_need_sign_in(
    client: AsyncClient, method: str, path: str, body: dict[str, Any] | None
) -> None:
    assert (await client.request(method, path, json=body)).status_code == 401


@pytest.mark.parametrize("role", list(STAFF_ROLE_PERMISSIONS))
async def test_deciding_an_invoice_never_answers_forbidden_for_a_record_the_caller_cannot_see(
    client: AsyncClient, auth_headers: AuthHeaders, role: str
) -> None:
    headers = await auth_headers(role)

    approve = await client.post(f"{INVOICES}/99999/approve", headers=headers)
    reject = await client.post(f"{INVOICES}/99999/reject", json={"comment": "x"}, headers=headers)

    assert (approve.status_code, reject.status_code) == (404, 404)


async def test_a_real_invoice_id_and_an_unknown_one_look_the_same_to_someone_who_cannot_read_invoices(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    invoice = await create_invoice(client, staff.officer, invoice_body(po, product))

    real = await client.get(f"{INVOICES}/{invoice['id']}", headers=staff.viewer)
    unknown = await client.get(f"{INVOICES}/99999", headers=staff.viewer)
    real_payments = await client.get(f"{INVOICES}/{invoice['id']}/payments", headers=staff.warehouse)
    unknown_payments = await client.get(f"{INVOICES}/99999/payments", headers=staff.warehouse)

    assert (real.status_code, real.json()) == (unknown.status_code, unknown.json())
    assert (real_payments.status_code, real_payments.json()) == (unknown_payments.status_code, unknown_payments.json())


async def test_an_outsider_cannot_decide_a_real_invoice_and_is_told_it_does_not_exist(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, auth_headers: AuthHeaders
) -> None:
    outsider = await auth_headers("employee")
    po = await received_po(client, staff, supplier, product)
    invoice = await create_invoice(client, staff.officer, invoice_body(po, product, unit_price="30.00"))
    await submit_invoice(client, staff.officer, invoice["id"])

    approve = await client.post(f"{INVOICES}/{invoice['id']}/approve", headers=outsider)
    reject = await client.post(f"{INVOICES}/{invoice['id']}/reject", json={"comment": "x"}, headers=outsider)

    assert (approve.status_code, reject.status_code) == (404, 404)
    assert approve.json() == {"detail": "Invoice not found"}


def test_the_new_permissions_are_described_and_given_to_the_right_roles() -> None:
    assert all(PERMISSIONS[code] for code in NEW_PERMISSIONS)
    holders = {code: {role for role, codes in ROLE_PERMISSIONS.items() if code in codes} for code in NEW_PERMISSIONS}
    assert holders == {
        "invoice:read": {"admin", "finance", "procurement_manager", "purchasing_officer"},
        "invoice:write": {"admin", "finance", "procurement_manager", "purchasing_officer"},
        "invoice:approve": {"admin", "finance"},
        "payment:write": {"admin", "finance"},
        "payment:release": {"admin", "finance"},
    }
