from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.inventory import InventoryTransaction
from app.models.product import Product
from app.models.supplier import Supplier
from tests.fixture_types import StockMatchesLedger
from tests.invoice_helpers import POS, Staff, ordered_po, receive

OPENING_STOCK = 50


async def test_a_plain_receipt_still_works_without_the_new_fields(
    client: AsyncClient,
    staff: Staff,
    supplier: Supplier,
    product: Product,
    assert_stock_matches_ledger: StockMatchesLedger,
) -> None:
    po = await ordered_po(client, staff, supplier, product)

    response = await client.post(
        f"{POS}/{po['id']}/receive",
        json={"items": [{"product_id": product.id, "quantity": 10}]},
        headers=staff.warehouse,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "received"
    assert response.json()["items"][0]["received_quantity"] == 10
    await assert_stock_matches_ledger(product.id)


async def test_only_accepted_units_enter_stock_and_count_as_received(
    client: AsyncClient,
    staff: Staff,
    supplier: Supplier,
    product: Product,
    db_session: AsyncSession,
    assert_stock_matches_ledger: StockMatchesLedger,
) -> None:
    po = await ordered_po(client, staff, supplier, product)

    response = await receive(client, staff, po["id"], product, 10, rejected=3, condition="damaged")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "partially_received"
    assert body["items"][0]["received_quantity"] == 7
    await db_session.refresh(product)
    assert product.current_stock == OPENING_STOCK + 7
    await assert_stock_matches_ledger(product.id)


async def test_rejected_units_stay_open_and_a_later_delivery_completes_the_order(
    client: AsyncClient,
    staff: Staff,
    supplier: Supplier,
    product: Product,
    assert_stock_matches_ledger: StockMatchesLedger,
) -> None:
    po = await ordered_po(client, staff, supplier, product)
    await receive(client, staff, po["id"], product, 10, rejected=4, condition="wrong_item")

    redelivery = await receive(client, staff, po["id"], product, 4)

    assert redelivery.status_code == 200
    assert redelivery.json()["status"] == "received"
    assert redelivery.json()["items"][0]["received_quantity"] == 10
    await assert_stock_matches_ledger(product.id)


async def test_the_order_is_received_only_when_accepted_units_reach_the_ordered_quantity(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await ordered_po(client, staff, supplier, product)

    first = await receive(client, staff, po["id"], product, 10, rejected=1)
    over_accepting = await receive(client, staff, po["id"], product, 2)

    assert first.json()["status"] == "partially_received"
    assert over_accepting.status_code == 400
    assert over_accepting.json()["detail"] == f"Cannot receive 2 units of product {product.id}; only 1 remain"


async def test_a_fully_rejected_delivery_changes_no_stock_and_leaves_the_order_open(
    client: AsyncClient,
    staff: Staff,
    supplier: Supplier,
    product: Product,
    db_session: AsyncSession,
    assert_stock_matches_ledger: StockMatchesLedger,
) -> None:
    po = await ordered_po(client, staff, supplier, product)

    response = await receive(client, staff, po["id"], product, 5, rejected=5, condition="damaged")

    assert response.status_code == 200
    assert response.json()["status"] == "ordered"
    assert response.json()["items"][0]["received_quantity"] == 0
    await db_session.refresh(product)
    assert product.current_stock == OPENING_STOCK
    movements = (
        await db_session.scalars(select(InventoryTransaction).where(InventoryTransaction.reference_po_id == po["id"]))
    ).all()
    assert movements == []
    await assert_stock_matches_ledger(product.id)


async def test_every_receive_writes_a_receipt_with_delivered_accepted_and_rejected_quantities(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await ordered_po(client, staff, supplier, product)
    await client.post(
        f"{POS}/{po['id']}/receive",
        json={
            "items": [
                {
                    "product_id": product.id,
                    "quantity": 6,
                    "rejected_quantity": 2,
                    "condition": "damaged",
                    "note": "Dented",
                }
            ],
            "note": "Morning truck",
        },
        headers=staff.warehouse,
    )
    await receive(client, staff, po["id"], product, 2)

    response = await client.get(f"{POS}/{po['id']}/receipts", headers=staff.viewer)

    receipts = response.json()
    assert response.status_code == 200
    assert [r["note"] for r in receipts] == ["Morning truck", None]
    first, second = receipts
    assert first["receiver"]["full_name"] == "Warehouse_Manager User"
    assert first["lines"][0]["delivered_quantity"] == 6
    assert first["lines"][0]["accepted_quantity"] == 4
    assert first["lines"][0]["rejected_quantity"] == 2
    assert first["lines"][0]["condition"] == "damaged"
    assert first["lines"][0]["note"] == "Dented"
    assert second["lines"][0]["condition"] == "good"
    assert second["lines"][0]["accepted_quantity"] == 2


async def test_the_receipt_list_is_empty_before_anything_arrives(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await ordered_po(client, staff, supplier, product)

    response = await client.get(f"{POS}/{po['id']}/receipts", headers=staff.viewer)

    assert response.status_code == 200
    assert response.json() == []


async def test_a_refused_receive_writes_no_receipt(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await ordered_po(client, staff, supplier, product)

    refused = await receive(client, staff, po["id"], product, 11)
    receipts = await client.get(f"{POS}/{po['id']}/receipts", headers=staff.viewer)

    assert refused.status_code == 400
    assert receipts.json() == []


async def test_receipts_of_an_unknown_order_are_not_found(client: AsyncClient, staff: Staff) -> None:
    response = await client.get(f"{POS}/9999/receipts", headers=staff.viewer)

    assert response.status_code == 404


async def test_receipts_need_sign_in(client: AsyncClient, staff: Staff, supplier: Supplier, product: Product) -> None:
    po = await ordered_po(client, staff, supplier, product)

    response = await client.get(f"{POS}/{po['id']}/receipts")

    assert response.status_code == 401


async def test_the_rejected_quantity_cannot_exceed_what_arrived(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await ordered_po(client, staff, supplier, product)

    response = await receive(client, staff, po["id"], product, 3, rejected=4)

    assert response.status_code == 422
    assert "rejected quantity" in response.text


async def test_a_negative_rejected_quantity_and_an_unknown_condition_are_refused(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await ordered_po(client, staff, supplier, product)

    negative = await receive(client, staff, po["id"], product, 3, rejected=-1)
    unknown = await receive(client, staff, po["id"], product, 3, condition="stolen")

    assert negative.status_code == 422
    assert unknown.status_code == 422


async def test_the_same_product_twice_in_one_receive_is_refused(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await ordered_po(client, staff, supplier, product)
    line = {"product_id": product.id, "quantity": 2}

    response = await client.post(f"{POS}/{po['id']}/receive", json={"items": [line, line]}, headers=staff.warehouse)

    assert response.status_code == 422


async def test_receiving_requires_the_inventory_permission(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await ordered_po(client, staff, supplier, product)

    response = await client.post(
        f"{POS}/{po['id']}/receive",
        json={"items": [{"product_id": product.id, "quantity": 1, "rejected_quantity": 1}]},
        headers=staff.officer,
    )

    assert response.status_code == 403


async def test_the_audit_entry_lists_arrived_and_rejected_quantities(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, db_session: AsyncSession
) -> None:
    po = await ordered_po(client, staff, supplier, product)
    await receive(client, staff, po["id"], product, 8, rejected=3)

    entry = await db_session.scalar(select(AuditLog).where(AuditLog.action == "po_received"))

    assert entry is not None
    assert entry.extra_data is not None
    assert entry.extra_data["items"] == {str(product.id): 8}
    assert entry.extra_data["rejected"] == {str(product.id): 3}


async def test_a_product_that_is_not_on_the_order_is_refused(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, db_session: AsyncSession
) -> None:
    other = Product(sku="OTHER-1", name="Other", cost=1, minimum_stock=0, supplier_id=supplier.id)
    db_session.add(other)
    await db_session.commit()
    po = await ordered_po(client, staff, supplier, product)

    response = await receive(client, staff, po["id"], other, 1)

    assert response.status_code == 400
    assert "is not on this purchase order" in response.json()["detail"]


async def test_a_delivery_with_rejections_marks_the_delivery_partial(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await ordered_po(client, staff, supplier, product)
    await receive(client, staff, po["id"], product, 10, rejected=2)

    deliveries = (await client.get("/api/v1/deliveries", headers=staff.viewer)).json()

    [delivery] = [row for row in deliveries["items"] if row["po_id"] == po["id"]]
    assert delivery["status"] == "partial"
    assert delivery["received_quantity"] == 8
