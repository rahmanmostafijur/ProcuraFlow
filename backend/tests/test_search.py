from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PaymentMethod, POStatus
from app.models.payment import PaymentRun
from app.models.product import Product
from app.models.purchase_request import PurchaseRequest
from app.models.role import Role
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice
from app.models.user import User
from tests.fixture_types import AuthHeaders, MakeUser
from tests.po_factory import build_po
from tests.portal_helpers import supplier_login

URL = "/api/v1/search"
ALL_SIX = {"purchase_order", "purchase_request", "supplier_invoice", "supplier", "product", "payment_run"}
PASSWORD = "TestPass123!"


@dataclass(frozen=True)
class Seed:
    supplier_id: int
    po_id: int
    request_id: int
    invoice_id: int
    product_id: int
    run_id: int
    requester_email: str


@pytest.fixture
async def seed(db_session: AsyncSession, make_user: MakeUser) -> Seed:
    """One record of every searchable type, each carrying the token "qx" so one query reaches them all."""
    admin = await make_user("seed-admin@example.com", "admin")
    requester = await make_user("requester@example.com", "employee")
    supplier = Supplier(name="Qx Zeta Supplies", email="orders@zeta-supplies.example")
    product = Product(sku="SKU-QX1", name="Zeta Sprocket", cost=5)
    db_session.add_all([supplier, product])
    await db_session.flush()
    po = build_po(
        po_number="PO-QX-7",
        supplier_id=supplier.id,
        created_by=admin.id,
        status=POStatus.ORDERED,
        lines=[(product.id, 1, Decimal(5))],
    )
    request = PurchaseRequest(
        request_number="REQ-QX-3", requester_id=requester.id, title="Hex bolts for line 4", currency_code="USD"
    )
    run = PaymentRun(number="PAY-QX-9", method=PaymentMethod.BANK_TRANSFER, currency_code="USD", created_by=admin.id)
    db_session.add_all([po, request, run])
    await db_session.flush()
    invoice = SupplierInvoice(
        supplier_id=supplier.id,
        po_id=po.id,
        invoice_number="INV-QX-5",
        invoice_date=date(2026, 1, 5),
        due_date=date(2026, 2, 5),
        currency_code="USD",
        created_by=admin.id,
    )
    db_session.add(invoice)
    await db_session.commit()
    return Seed(supplier.id, po.id, request.id, invoice.id, product.id, run.id, requester.email)


async def search(client: AsyncClient, headers: dict[str, str], q: str, **params: Any) -> dict[str, Any]:
    response = await client.get(URL, params={"q": q, **params}, headers=headers)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def group_types(body: dict[str, Any]) -> list[str]:
    return [group["type"] for group in body["groups"]]


def item_ids(body: dict[str, Any], group_type: str) -> list[int]:
    return [item["id"] for group in body["groups"] if group["type"] == group_type for item in group["items"]]


@pytest.mark.parametrize(
    ("q", "group_type", "id_field"),
    [
        ("PO-QX-7", "purchase_order", "po_id"),
        ("zeta supplies", "purchase_order", "po_id"),
        ("REQ-QX-3", "purchase_request", "request_id"),
        ("hex bolts", "purchase_request", "request_id"),
        ("INV-QX-5", "supplier_invoice", "invoice_id"),
        ("zeta supplies", "supplier_invoice", "invoice_id"),
        ("orders@zeta", "supplier", "supplier_id"),
        ("zeta supplies", "supplier", "supplier_id"),
        ("SKU-QX1", "product", "product_id"),
        ("zeta sprocket", "product", "product_id"),
        ("PAY-QX-9", "payment_run", "run_id"),
    ],
)
async def test_each_type_is_found_by_each_field(
    client: AsyncClient, auth_headers: AuthHeaders, seed: Seed, q: str, group_type: str, id_field: str
) -> None:
    headers = await auth_headers("finance")

    body = await search(client, headers, q)

    assert getattr(seed, id_field) in item_ids(body, group_type)


async def test_matching_ignores_case(client: AsyncClient, auth_headers: AuthHeaders, seed: Seed) -> None:
    headers = await auth_headers("finance")

    lower = await search(client, headers, "po-qx-7")
    upper = await search(client, headers, "PO-QX-7")

    assert item_ids(lower, "purchase_order") == [seed.po_id] == item_ids(upper, "purchase_order")


async def test_response_shape_and_urls(client: AsyncClient, auth_headers: AuthHeaders, seed: Seed) -> None:
    headers = await auth_headers("finance")

    body = await search(client, headers, "qx")

    assert body["query"] == "qx"
    by_type = {group["type"]: group for group in body["groups"]}
    assert set(by_type) == ALL_SIX
    assert by_type["purchase_order"]["label"] == "Purchase orders"
    assert by_type["purchase_order"]["items"][0] == {
        "id": seed.po_id,
        "title": "PO-QX-7",
        "subtitle": "Qx Zeta Supplies",
        "status": "ordered",
        "url": f"/purchase-orders/{seed.po_id}",
    }
    assert by_type["purchase_request"]["items"][0]["url"] == f"/requests/{seed.request_id}"
    assert by_type["supplier_invoice"]["items"][0]["url"] == f"/invoices/{seed.invoice_id}"
    assert by_type["product"]["items"][0]["url"] == "/products?search=SKU-QX1"
    assert by_type["product"]["items"][0]["status"] is None
    assert by_type["payment_run"]["items"][0]["url"] == "/payment-runs"


async def test_supplier_link_depends_on_who_can_open_the_detail_page(
    client: AsyncClient, auth_headers: AuthHeaders, seed: Seed
) -> None:
    manager = await auth_headers("procurement_manager")
    viewer = await auth_headers("viewer")

    managed = await search(client, manager, "orders@zeta")
    viewed = await search(client, viewer, "orders@zeta")

    assert managed["groups"][0]["items"][0]["url"] == f"/suppliers/{seed.supplier_id}"
    assert viewed["groups"][0]["items"][0]["url"] == "/suppliers?search=Qx%20Zeta%20Supplies"


@pytest.mark.parametrize("q", ["", "a", " a ", "   "])
async def test_short_query_returns_no_groups(
    client: AsyncClient, auth_headers: AuthHeaders, seed: Seed, q: str
) -> None:
    headers = await auth_headers("admin")

    body = await search(client, headers, q)

    assert body["groups"] == []


async def test_missing_query_returns_no_groups(client: AsyncClient, auth_headers: AuthHeaders, seed: Seed) -> None:
    headers = await auth_headers("admin")

    response = await client.get(URL, headers=headers)

    assert response.status_code == 200
    assert response.json() == {"query": "", "groups": []}


@pytest.mark.parametrize("q", ["%%", "__", "_%", "q%", "\\", "%\\%"])
async def test_wildcards_do_not_widen_the_match(
    client: AsyncClient, auth_headers: AuthHeaders, seed: Seed, q: str
) -> None:
    headers = await auth_headers("admin")

    body = await search(client, headers, q)

    assert body["groups"] == []


async def test_a_literal_percent_sign_still_matches_itself(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession, seed: Seed
) -> None:
    db_session.add(Product(sku="SALE-1", name="Save 50% now", cost=1))
    await db_session.commit()
    headers = await auth_headers("admin")

    literal = await search(client, headers, "50%")
    widened = await search(client, headers, "5%")

    assert group_types(literal) == ["product"]
    assert widened["groups"] == []


@pytest.mark.parametrize("q", ["'; DROP TABLE suppliers; --", "x' OR '1'='1", '" OR 1=1 --', "1; SELECT pg_sleep(5)"])
async def test_sql_looking_input_is_inert(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession, seed: Seed, q: str
) -> None:
    headers = await auth_headers("admin")

    body = await search(client, headers, q)

    assert body["groups"] == []
    assert await db_session.scalar(select(func.count()).select_from(Supplier)) == 1


async def test_limit_defaults_to_five_per_group_and_is_capped_at_ten(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession
) -> None:
    db_session.add_all(Supplier(name=f"Bulk Co {number:02d}") for number in range(12))
    await db_session.commit()
    headers = await auth_headers("viewer")

    default = await search(client, headers, "bulk co")
    two = await search(client, headers, "bulk co", limit=2)
    capped = await search(client, headers, "bulk co", limit=50)

    assert len(item_ids(default, "supplier")) == 5
    assert len(item_ids(two, "supplier")) == 2
    assert len(item_ids(capped, "supplier")) == 10


async def test_limit_below_one_is_refused(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("viewer")

    response = await client.get(URL, params={"q": "bulk", "limit": 0}, headers=headers)

    assert response.status_code == 422


async def test_exact_then_prefix_then_most_recent(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession
) -> None:
    now = datetime.now(UTC)
    names = ["Super Pipe", "Pipe Works", "pipe", "Acme Pipe Co", "Old Pipe Yard"]
    # Created oldest first, except that "Old Pipe Yard" is the oldest of all.
    stamps = [now - timedelta(days=4), now - timedelta(days=3), now - timedelta(days=2), now - timedelta(days=1)]
    suppliers = [Supplier(name=name, created_at=at) for name, at in zip(names, stamps, strict=False)]
    suppliers.append(Supplier(name=names[4], created_at=now - timedelta(days=9)))
    db_session.add_all(suppliers)
    await db_session.commit()
    headers = await auth_headers("viewer")

    body = await search(client, headers, "Pipe")

    titles = [item["title"] for item in body["groups"][0]["items"]]
    assert titles == ["pipe", "Pipe Works", "Acme Pipe Co", "Super Pipe", "Old Pipe Yard"]


# What each role sees when a record of every type matches. Requests are the requester's own unless request:read_all.
VISIBLE_GROUPS = {
    "viewer": {"purchase_order", "supplier", "product"},
    "warehouse_manager": {"purchase_order", "supplier", "product"},
    "employee": {"purchase_order", "supplier", "product"},
    "department_manager": {"purchase_order", "supplier", "product"},
    "purchasing_officer": ALL_SIX,
    "procurement_manager": ALL_SIX,
    "finance": ALL_SIX,
    "admin": ALL_SIX,
}


@pytest.mark.parametrize("role", sorted(VISIBLE_GROUPS))
async def test_groups_follow_the_role(client: AsyncClient, auth_headers: AuthHeaders, seed: Seed, role: str) -> None:
    headers = await auth_headers(role)

    body = await search(client, headers, "qx")

    assert set(group_types(body)) == VISIBLE_GROUPS[role]
    assert len(group_types(body)) == len(VISIBLE_GROUPS[role])


async def test_requester_sees_their_own_request_only(
    client: AsyncClient, auth_headers: AuthHeaders, seed: Seed
) -> None:
    owner = await client.post("/api/v1/auth/login", json={"email": seed.requester_email, "password": PASSWORD})
    owner_headers = {"Authorization": f"Bearer {owner.json()['access_token']}"}
    other_headers = await auth_headers("employee", email="other-employee@example.com")

    mine = await search(client, owner_headers, "qx")
    theirs = await search(client, other_headers, "qx")

    assert item_ids(mine, "purchase_request") == [seed.request_id]
    assert "purchase_request" not in group_types(theirs)


async def test_role_without_invoice_read_cannot_find_invoices_or_runs_by_number(
    client: AsyncClient, auth_headers: AuthHeaders, seed: Seed
) -> None:
    headers = await auth_headers("warehouse_manager")

    invoice = await search(client, headers, "INV-QX-5")
    run = await search(client, headers, "PAY-QX-9")

    assert invoice["groups"] == []
    assert run["groups"] == []


async def test_supplier_portal_account_is_refused(
    client: AsyncClient,
    db_session: AsyncSession,
    roles: dict[str, Role],
    supplier: Supplier,
) -> None:
    headers = await supplier_login(client, db_session, roles, supplier, "portal@supplier.example.com")

    response = await client.get(URL, params={"q": "test"}, headers=headers)

    assert response.status_code == 403


async def test_anonymous_request_is_refused(client: AsyncClient) -> None:
    response = await client.get(URL, params={"q": "test"})

    assert response.status_code == 401


async def test_deactivated_user_is_refused(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession
) -> None:
    headers = await auth_headers("viewer", email="gone@example.com")
    user = (await db_session.execute(select(User).where(User.email == "gone@example.com"))).scalar_one()
    user.is_active = False
    await db_session.commit()

    response = await client.get(URL, params={"q": "test"}, headers=headers)

    assert response.status_code == 401
