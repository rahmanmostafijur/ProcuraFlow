"""Every number that more than one screen shows must come out identical through each of them."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_today
from app.models.enums import COMMITTED_PO_STATUSES, POStatus
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User
from app.schemas.common import format_money
from app.services import metrics_service
from tests.fixture_types import AuthHeaders, MakeUser
from tests.flow_helpers import API, submitted_po, user_id
from tests.invoice_helpers import INVOICES, add_rate, approved_invoice, make_staff, matched_invoice, received_po
from tests.po_factory import build_po

SPEND_BY_SUPPLIER_URL = "/api/v1/reports/supplier-performance"
MONTHLY_TRENDS_URL = "/api/v1/dashboard/monthly-trends"
MAX_MONTHS = 24


async def _seed_mixed_orders(db: AsyncSession, product: Product, creator_id: int) -> None:
    """One order per status, alternating dollars and euros (euros converted at 1.25), plus a second supplier."""
    other = Supplier(name="Second Supplier", email="second@example.com")
    db.add(other)
    await db.flush()
    for index, po_status in enumerate(POStatus):
        in_euros = index % 2 == 1
        db.add(
            build_po(
                po_number=f"PO-MIX-{index}",
                supplier_id=other.id if index % 3 == 0 else product.supplier_id,
                created_by=creator_id,
                status=po_status,
                lines=[(product.id, index + 1, Decimal("10.00"))],
                currency_code="EUR" if in_euros else "USD",
                exchange_rate=Decimal("1.25") if in_euros else Decimal(1),
            )
        )
    await db.commit()


async def test_spend_by_supplier_and_by_month_add_up_to_the_same_total(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: AuthHeaders,
    make_user: MakeUser,
    product: Product,
) -> None:
    headers = await auth_headers("viewer")
    creator = await make_user("creator@example.com", "procurement_manager")
    await _seed_mixed_orders(db_session, product, creator.id)

    by_supplier = (await client.get(SPEND_BY_SUPPLIER_URL, headers=headers)).json()
    by_month = (await client.get(MONTHLY_TRENDS_URL, params={"months": MAX_MONTHS}, headers=headers)).json()
    context = await metrics_service.get_context(db_session)
    from_service = await metrics_service.committed_spend_by_month(db_session, context, MAX_MONTHS)

    supplier_total = sum(Decimal(row["total_spend"]) for row in by_supplier)
    month_total = sum(Decimal(row["total_spend"]) for row in by_month)
    service_total = sum(row.total_spend for row in from_service)
    assert supplier_total == month_total == service_total
    assert supplier_total > 0
    assert sum(row["order_count"] for row in by_supplier) == sum(row["order_count"] for row in by_month)
    assert sum(row["order_count"] for row in by_month) == len(COMMITTED_PO_STATUSES)


async def test_foreign_currency_orders_count_at_their_locked_base_amount(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: AuthHeaders,
    make_user: MakeUser,
    product: Product,
) -> None:
    headers = await auth_headers("viewer")
    creator = await make_user("creator@example.com", "procurement_manager")
    db_session.add(
        build_po(
            po_number="PO-EUR-1",
            supplier_id=product.supplier_id,
            created_by=creator.id,
            status=POStatus.ORDERED,
            lines=[(product.id, 10, Decimal("10.00"))],
            currency_code="EUR",
            exchange_rate=Decimal(2),
        )
    )
    await db_session.commit()

    rows = (await client.get(SPEND_BY_SUPPLIER_URL, headers=headers)).json()

    [row] = [r for r in rows if r["supplier_id"] == product.supplier_id]
    assert row["total_spend"] == "200.00"


async def test_the_company_time_zone_decides_which_month_an_order_belongs_to(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: AuthHeaders,
    make_user: MakeUser,
    product: Product,
) -> None:
    admin = await auth_headers("admin")
    creator = await make_user("creator@example.com", "procurement_manager")
    # 20:00 UTC on 31 March is already 1 April in Tokyo.
    late_march = build_po(
        po_number="PO-TZ-1",
        supplier_id=product.supplier_id,
        created_by=creator.id,
        status=POStatus.APPROVED,
        lines=[(product.id, 1, Decimal("10.00"))],
    )
    late_march.created_at = datetime(2026, 3, 31, 20, 0, tzinfo=UTC)
    db_session.add(late_march)
    await db_session.commit()

    in_utc = (await client.get(MONTHLY_TRENDS_URL, params={"months": MAX_MONTHS}, headers=admin)).json()
    await client.patch("/api/v1/company-settings", json={"timezone": "Asia/Tokyo"}, headers=admin)
    in_tokyo = (await client.get(MONTHLY_TRENDS_URL, params={"months": MAX_MONTHS}, headers=admin)).json()

    assert [row["month"] for row in in_utc] == ["2026-03"]
    assert [row["month"] for row in in_tokyo] == ["2026-04"]


async def test_the_approvals_badge_equals_the_length_of_the_queue_it_links_to(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession, supplier: Supplier, product: Product
) -> None:
    officer = await auth_headers("purchasing_officer")
    employee = await auth_headers("employee")
    manager = await auth_headers("procurement_manager")
    viewer = await auth_headers("viewer")
    await submitted_po(client, officer, supplier, product)
    await submitted_po(client, officer, supplier, product)
    request = (
        await client.post(
            f"{API}/purchase-requests",
            json={"title": "Desk", "lines": [{"description": "Desk", "quantity": 1, "estimated_unit_price": "300"}]},
            headers=employee,
        )
    ).json()
    await client.post(f"{API}/purchase-requests/{request['id']}/submit", headers=employee)

    for headers, expected in ((manager, 3), (officer, 0), (employee, 0), (viewer, 0)):
        user = await db_session.get(User, await user_id(client, headers))
        assert user is not None
        queue_page = (await client.get(f"{API}/approvals/queue", headers=headers)).json()
        assert queue_page["total"] == len(queue_page["items"]) == expected
        assert await metrics_service.pending_approval_count(db_session, user) == expected


async def test_budget_figures_agree_with_the_spend_report(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: AuthHeaders,
    make_user: MakeUser,
    product: Product,
) -> None:
    finance = await auth_headers("finance")
    creator = await make_user("creator@example.com", "procurement_manager")
    centre = (
        await client.post(f"{API}/cost-centres", json={"code": "MKT", "name": "Marketing"}, headers=finance)
    ).json()
    await client.put(
        f"{API}/budgets",
        json={"cost_centre_id": centre["id"], "fiscal_year": utc_today().year, "amount": "100000"},
        headers=finance,
    )
    for index, (status, price) in enumerate(
        (
            (POStatus.APPROVED, "120.00"),
            (POStatus.ORDERED, "80.50"),
            (POStatus.RECEIVED, "300.25"),
            (POStatus.DRAFT, "9.00"),
        )
    ):
        db_session.add(
            build_po(
                po_number=f"PO-BUD-{index}",
                supplier_id=product.supplier_id,
                created_by=creator.id,
                status=status,
                lines=[(product.id, 1, Decimal(price))],
                cost_centre_id=centre["id"],
                approved_at=datetime.now(UTC),
            )
        )
    await db_session.commit()

    [position] = (await client.get(f"{API}/budgets", headers=finance)).json()
    spend = (await client.get(SPEND_BY_SUPPLIER_URL, headers=finance)).json()

    # Every committed order belongs to this one supplier and cost centre, so the report's spend is exactly the
    # budget screen's spent plus committed.
    [row] = [r for r in spend if r["supplier_id"] == product.supplier_id]
    assert Decimal(position["spent"]) + Decimal(position["committed"]) == Decimal(row["total_spend"])
    assert Decimal(position["remaining"]) == Decimal(position["budget"]) - Decimal(row["total_spend"])


async def test_dashboard_counts_match_the_purchase_order_lists(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: AuthHeaders,
    make_user: MakeUser,
    product: Product,
) -> None:
    headers = await auth_headers("viewer")
    creator = await make_user("creator@example.com", "procurement_manager")
    await _seed_mixed_orders(db_session, product, creator.id)

    summary = (await client.get("/api/v1/dashboard/summary", headers=headers)).json()
    everything = (await client.get("/api/v1/purchase-orders", params={"page_size": 1}, headers=headers)).json()

    async def listed(*statuses: POStatus) -> int:
        total = 0
        for po_status in statuses:
            page = await client.get(
                "/api/v1/purchase-orders", params={"status": po_status.value, "page_size": 1}, headers=headers
            )
            total += page.json()["total"]
        return int(total)

    assert summary["total_purchase_orders"] == everything["total"] == len(POStatus)
    assert summary["pending_orders"] == await listed(*metrics_service.PENDING_PO_STATUSES)
    assert summary["completed_orders"] == await listed(*metrics_service.COMPLETED_PO_STATUSES)
    assert (
        summary["supplier_count"]
        == (await client.get("/api/v1/suppliers", params={"is_active": True}, headers=headers)).json()["total"]
    )


async def test_payables_and_invoice_counts_agree_between_dashboard_invoice_list_and_service(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    staff = await make_staff(auth_headers)
    await add_rate(client, staff.finance, "EUR", "2")
    for number, currency in (("A-USD", "USD"), ("B-EUR", "EUR")):
        po = await received_po(client, staff, supplier, product, currency_code=currency)
        await approved_invoice(client, staff, po, product, number=number)
    late_po = await received_po(client, staff, supplier, product)
    await approved_invoice(
        client,
        staff,
        late_po,
        product,
        number="C-LATE",
        invoice_date=(utc_today() - timedelta(days=40)).isoformat(),
        due_date=(utc_today() - timedelta(days=2)).isoformat(),
    )
    matched_po = await received_po(client, staff, supplier, product)
    await matched_invoice(client, staff, matched_po, product, number="D-MATCHED")

    summary = (await client.get("/api/v1/dashboard/summary", headers=staff.viewer)).json()
    listing = (await client.get(INVOICES, headers=staff.finance)).json()
    context = await metrics_service.get_context(db_session)
    approved_only = (await client.get(INVOICES, params={"status": "approved"}, headers=staff.finance)).json()
    overdue_only = (
        await client.get(INVOICES, params={"due_before": utc_today().isoformat()}, headers=staff.finance)
    ).json()

    assert summary["payables_outstanding"] == "400.00"
    assert summary["payables_outstanding"] == listing["totals"]["payables_outstanding"]
    assert summary["payables_outstanding"] == approved_only["totals"]["payables_outstanding"]
    assert summary["payables_outstanding"] == format_money(
        await metrics_service.payables_outstanding(db_session, context)
    )
    assert summary["payables_overdue"] == "100.00"
    assert summary["payables_overdue"] == listing["totals"]["payables_overdue"]
    assert summary["payables_overdue"] == overdue_only["totals"]["payables_overdue"]
    assert summary["payables_overdue"] == format_money(await metrics_service.payables_overdue(db_session, context))
    assert summary["invoices_needing_attention"] == listing["totals"]["needing_attention"] == 1
    assert summary["invoices_needing_attention"] == await metrics_service.invoices_needing_attention(db_session)
    by_status = listing["totals"]["by_status"]
    assert by_status["approved"] == approved_only["total"] == 3
    assert sum(by_status.values()) == listing["total"] == 4
