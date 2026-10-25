"""Creating and editing draft purchase orders: validation, pricing and the audit trail of what changed."""

from collections.abc import Iterable, Mapping
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.money import trim_money
from app.models.currency import Currency
from app.models.enums import POStatus
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.supplier import Supplier
from app.models.user import User
from app.schemas.purchase_order import PurchaseOrderCreate, PurchaseOrderUpdate
from app.services import po_pricing
from app.services.audit_service import current_values, field_changes
from app.services.currency_service import get_active_currency
from app.services.po_pricing import LineSpec
from app.services.purchase_order_service import generate_po_number

AUDITED_LINE_FIELDS = ("product_id", "quantity", "unit_price", "tax_rate_id")


def _audited_lines(lines: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    audited = []
    for line in lines:
        entry: dict[str, Any] = {
            "product_id": line["product_id"],
            "quantity": line["quantity"],
            # So 10, 10.00 and 10.0000 are the same figure in the audit log.
            "unit_price": trim_money(line["unit_price"]),
        }
        if line.get("tax_rate_id") is not None:
            entry["tax_rate_id"] = line["tax_rate_id"]
        audited.append(entry)
    # Sorted by product so that reordering otherwise identical lines is not reported as a change.
    return sorted(audited, key=lambda entry: entry["product_id"])


async def _ensure_products_exist(db: AsyncSession, product_ids: set[int]) -> None:
    found = set((await db.execute(select(Product.id).where(Product.id.in_(product_ids)))).scalars().all())
    missing = product_ids - found
    if missing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown product ids: {sorted(missing)}")


async def _specs_from_payload(db: AsyncSession, items: Iterable[Mapping[str, Any]]) -> list[LineSpec]:
    rows = list(items)
    await _ensure_products_exist(db, {row["product_id"] for row in rows})
    snapshots = await po_pricing.resolve_tax_snapshots(
        db, (row["tax_rate_id"] for row in rows if row.get("tax_rate_id") is not None)
    )
    return [
        LineSpec(
            product_id=row["product_id"],
            quantity=row["quantity"],
            unit_price=row["unit_price"],
            tax=snapshots[row["tax_rate_id"]] if row.get("tax_rate_id") is not None else po_pricing.NO_TAX,
        )
        for row in rows
    ]


async def create_draft(db: AsyncSession, payload: PurchaseOrderCreate, creator: User) -> PurchaseOrder:
    supplier = await db.get(Supplier, payload.supplier_id)
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Supplier not found")

    currency = await po_pricing.resolve_currency(db, payload.currency_code, supplier)
    specs = await _specs_from_payload(db, (item.model_dump() for item in payload.items))
    items, totals = po_pricing.price_lines(specs, currency)

    po = PurchaseOrder(
        po_number=await generate_po_number(db),
        supplier_id=payload.supplier_id,
        currency_code=currency.code,
        expected_delivery_date=payload.expected_delivery_date,
        notes=payload.notes,
        created_by=creator.id,
        status=POStatus.DRAFT,
    )
    po.items = items
    po_pricing.apply_totals(po, totals)
    db.add(po)
    await db.flush()
    return po


async def update_draft(db: AsyncSession, po: PurchaseOrder, payload: PurchaseOrderUpdate) -> dict[str, Any]:
    """Apply an edit to a draft and return the audit description of what changed."""
    if po.status != POStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft purchase orders can be edited")

    update_data = payload.model_dump(exclude_unset=True)
    items_data = update_data.pop("items", None)
    requested_currency = update_data.pop("currency_code", None)
    changes = field_changes(current_values(po, update_data), update_data)
    for field, value in update_data.items():
        setattr(po, field, value)

    currency: Currency | None = None
    if requested_currency is not None and requested_currency != po.currency_code:
        currency = await get_active_currency(db, requested_currency)
        changes["currency_code"] = {"from": po.currency_code, "to": currency.code}

    if items_data is None and currency is None:
        return changes

    if items_data is not None:
        specs = await _specs_from_payload(db, items_data)
        previous_lines = _audited_lines(current_values(item, AUDITED_LINE_FIELDS) for item in po.items)
        changes = {**changes, **field_changes({"items": previous_lines}, {"items": _audited_lines(items_data)})}
    else:
        # Only the currency changed: the lines keep the tax they were priced with and are re-rounded.
        specs = po_pricing.specs_from_items(po.items)

    pricing_currency = currency or await db.get(Currency, po.currency_code)
    assert pricing_currency is not None  # noqa: S101 - the order references it by foreign key
    items, totals = po_pricing.price_lines(specs, pricing_currency)

    po.items.clear()
    # Delete the old lines first; the unit of work would otherwise insert the new ones before
    # removing the orphans and trip the one-line-per-product constraint.
    await db.flush()
    po.items = items
    po.currency_code = pricing_currency.code
    po_pricing.apply_totals(po, totals)
    return changes
