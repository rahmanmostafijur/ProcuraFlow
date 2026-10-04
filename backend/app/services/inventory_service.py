from collections.abc import Iterable

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import InventoryTransactionType
from app.models.inventory import InventoryTransaction
from app.models.product import Product


async def lock_products(db: AsyncSession, product_ids: Iterable[int]) -> dict[int, Product]:
    # Lock order is purchase order first, then products by ascending id, in one statement.
    # Every writer follows it, so concurrent receipts and adjustments cannot deadlock.
    result = await db.execute(
        select(Product)
        .where(Product.id.in_(set(product_ids)))
        .order_by(Product.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return {product.id: product for product in result.scalars()}


async def apply_inventory_transaction(
    db: AsyncSession,
    *,
    product: Product,
    quantity_delta: int,
    transaction_type: InventoryTransactionType,
    created_by: int,
    reference_po_id: int | None = None,
    reason: str | None = None,
) -> InventoryTransaction:
    new_stock = product.current_stock + quantity_delta
    if new_stock < 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Adjustment would result in negative stock for product '{product.sku}'",
        )
    product.current_stock = new_stock

    transaction = InventoryTransaction(
        product_id=product.id,
        type=transaction_type,
        quantity_delta=quantity_delta,
        resulting_stock=new_stock,
        reference_po_id=reference_po_id,
        reason=reason,
        created_by=created_by,
    )
    db.add(transaction)
    return transaction
