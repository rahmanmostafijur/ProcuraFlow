from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email import EmailOutbox
from app.models.enums import POStatus
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.supplier import Supplier
from app.models.user import User
from tests.fixture_types import AuthHeaders
from tests.po_factory import build_po

BASE = "/api/v1/purchase-orders"


async def _po(
    db: AsyncSession, supplier: Supplier, product: Product, status: POStatus = POStatus.ORDERED
) -> PurchaseOrder:
    creator = (await db.execute(select(User.id).limit(1))).scalar_one()
    po = build_po(
        po_number="PO-DOC-1",
        supplier_id=supplier.id,
        created_by=creator,
        status=status,
        lines=[(product.id, 3, Decimal("12.50"))],
    )
    db.add(po)
    await db.commit()
    await db.refresh(po)
    return po


async def test_pdf_download_returns_a_pdf(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession, supplier: Supplier, product: Product
) -> None:
    headers = await auth_headers("purchasing")
    po = await _po(db_session, supplier, product)
    response = await client.get(f"{BASE}/{po.id}/pdf", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "PO-DOC-1.pdf" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")


async def test_pdf_needs_sign_in_and_a_real_order(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession, supplier: Supplier, product: Product
) -> None:
    po = await _po(db_session, supplier, product)
    assert (await client.get(f"{BASE}/{po.id}/pdf")).status_code == 401
    headers = await auth_headers("purchasing")
    assert (await client.get(f"{BASE}/999999/pdf", headers=headers)).status_code == 404


async def test_send_queues_one_email_to_the_supplier(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession, supplier: Supplier, product: Product
) -> None:
    headers = await auth_headers("purchasing")
    po = await _po(db_session, supplier, product)
    response = await client.post(f"{BASE}/{po.id}/send", headers=headers)
    assert response.status_code == 202
    rows = (await db_session.execute(select(EmailOutbox))).scalars().all()
    assert [r.to_address for r in rows] == ["supplier@example.com"]
    assert "PO-DOC-1" in rows[0].subject
    assert "USD 37.50" in rows[0].body


async def test_send_refuses_an_order_that_is_not_ordered(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession, supplier: Supplier, product: Product
) -> None:
    headers = await auth_headers("purchasing")
    po = await _po(db_session, supplier, product, POStatus.DRAFT)
    assert (await client.post(f"{BASE}/{po.id}/send", headers=headers)).status_code == 409


async def test_send_refuses_a_supplier_without_email(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession, supplier: Supplier, product: Product
) -> None:
    headers = await auth_headers("purchasing")
    supplier.email = None
    po = await _po(db_session, supplier, product)
    assert (await client.post(f"{BASE}/{po.id}/send", headers=headers)).status_code == 422


async def test_send_needs_the_transition_permission(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession, supplier: Supplier, product: Product
) -> None:
    headers = await auth_headers("viewer")
    po = await _po(db_session, supplier, product)
    assert (await client.post(f"{BASE}/{po.id}/send", headers=headers)).status_code == 403
