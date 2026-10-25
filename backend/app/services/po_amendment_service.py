"""Amending a purchase order after it was placed: versions, a readable diff, and approval when the total rises.

* An amendment that does not raise the total is applied straight away and recorded as a new version.
* One that raises the total is stored as a pending version and goes through approval like any document; the order is
  untouched until it is approved. It uses the order's locked exchange rate, so only base-currency amounts move.
* Lines that were already received cannot be removed or cut below what arrived, and the order's status never changes.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.money import convert_to_base
from app.models.currency import Currency
from app.models.enums import AmendmentStatus, ApprovalDocumentType, POStatus
from app.models.po_version import PurchaseOrderVersion
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.user import User
from app.schemas.po_version import PurchaseOrderAmend
from app.services import approval_adapters, approval_engine, po_draft_service, po_pricing
from app.services.audit_service import record_audit_event
from app.services.company_settings_service import get_company_settings
from app.services.po_diff import diff_snapshots, snapshot_from_parts, snapshot_of
from app.services.po_pricing import LineSpec, TaxSnapshot
from app.services.purchase_order_service import get_purchase_order_for_update

AMENDABLE = (POStatus.APPROVED, POStatus.ORDERED, POStatus.PARTIALLY_RECEIVED)


def _error(code: int, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail=message)


async def _product_names(db: AsyncSession, product_ids: set[int]) -> dict[int, tuple[str, str]]:
    rows = (await db.execute(select(Product.id, Product.sku, Product.name).where(Product.id.in_(product_ids)))).all()
    return {row.id: (row.sku, row.name) for row in rows}


async def list_versions(db: AsyncSession, po_id: int) -> list[PurchaseOrderVersion]:
    stmt = (
        select(PurchaseOrderVersion).where(PurchaseOrderVersion.po_id == po_id).order_by(PurchaseOrderVersion.version)
    )
    return list((await db.execute(stmt)).scalars().all())


async def _ensure_first_version(db: AsyncSession, po: PurchaseOrder) -> None:
    """Version 1 is the order as it stood before the first amendment, kept so the first diff has a starting point."""
    if await db.scalar(
        select(func.count()).select_from(PurchaseOrderVersion).where(PurchaseOrderVersion.po_id == po.id)
    ):
        return
    names = await _product_names(db, {item.product_id for item in po.items})
    db.add(
        PurchaseOrderVersion(
            po_id=po.id,
            version=1,
            status=AmendmentStatus.APPLIED,
            snapshot=snapshot_of(po, names),
            changes=[],
            reason="Order as first approved",
            created_by=po.approved_by or po.created_by,
            decided_at=po.approved_at,
        )
    )
    await db.flush()


def _check_received_lines(po: PurchaseOrder, new_quantities: dict[int, int]) -> None:
    received = {item.product_id: item.received_quantity for item in po.items}
    for product_id, quantity in received.items():
        if quantity == 0:
            continue
        if product_id not in new_quantities:
            raise _error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"Product {product_id} has already been received ({quantity}) and cannot be removed from the order",
            )
        if new_quantities[product_id] < quantity:
            raise _error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"Product {product_id} cannot be reduced below the {quantity} already received",
            )
    if po.status == POStatus.PARTIALLY_RECEIVED and sum(new_quantities.values()) <= sum(received.values()):
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Everything that would remain on the order has already been received; receive or cancel it instead",
        )


async def amend_purchase_order(
    db: AsyncSession, po: PurchaseOrder, payload: PurchaseOrderAmend, actor: User
) -> PurchaseOrderVersion:
    """Propose a change to a placed order. The caller must hold the order's row lock and commit afterwards."""
    if po.status not in AMENDABLE:
        raise _error(status.HTTP_409_CONFLICT, f"A purchase order that is '{po.status.value}' cannot be amended")
    versions = await list_versions(db, po.id)
    if any(version.status == AmendmentStatus.PENDING_APPROVAL for version in versions):
        raise _error(status.HTTP_409_CONFLICT, "An earlier amendment is still waiting for approval")
    await _ensure_first_version(db, po)

    currency = await db.get(Currency, po.currency_code)
    assert currency is not None  # noqa: S101 - the order references it by foreign key
    fields = payload.model_dump(exclude_unset=True)
    if payload.items is not None:
        specs = await po_draft_service.specs_from_payload(db, fields["items"])
    else:
        specs = po_pricing.specs_from_items(po.items)
    new_items, totals = po_pricing.price_lines(specs, currency)
    _check_received_lines(po, {item.product_id: item.quantity for item in new_items})

    names = await _product_names(db, {item.product_id for item in po.items} | {item.product_id for item in new_items})
    before = snapshot_of(po, names)
    after = snapshot_from_parts(
        currency_code=po.currency_code,
        expected_delivery_date=fields.get("expected_delivery_date", po.expected_delivery_date),
        notes=fields.get("notes", po.notes),
        items=new_items,
        totals=(totals.subtotal, totals.tax_total, totals.grand_total),
        product_names=names,
    )
    changes = diff_snapshots(before, after)
    if not changes:
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Nothing would change")

    base_code = (await get_company_settings(db)).base_currency_code
    base_currency = await db.get(Currency, base_code)
    assert base_currency is not None  # noqa: S101 - the settings row references it by foreign key
    rate = po.exchange_rate if po.exchange_rate is not None else Decimal(1)
    increase = totals.grand_total - po.grand_total
    raises_total = increase > 0
    after["budget_increase_base"] = (
        str(convert_to_base(increase, rate, base_currency.minor_units)) if raises_total else "0"
    )

    next_version = max(version.version for version in versions) + 1 if versions else 2
    version = PurchaseOrderVersion(
        po_id=po.id,
        version=next_version,
        status=AmendmentStatus.PENDING_APPROVAL if raises_total else AmendmentStatus.APPLIED,
        snapshot=after,
        changes=changes,
        reason=payload.reason,
        created_by=actor.id,
    )
    db.add(version)
    await db.flush()

    if not raises_total:
        await apply_version(db, po, version, actor)
        return version

    new_total_base = convert_to_base(totals.grand_total, rate, base_currency.minor_units)
    await approval_engine.open_round(db, approval_adapters.amendment_subject(version, po, actor, new_total_base))
    await record_audit_event(
        db,
        user_id=actor.id,
        action="po_amendment_submitted",
        entity_type="purchase_order",
        entity_id=po.id,
        extra_data={"version": next_version, "reason": payload.reason, "increase": str(increase)},
    )
    return version


async def apply_version(db: AsyncSession, po: PurchaseOrder, version: PurchaseOrderVersion, actor: User) -> None:
    """Make the order look like the version's snapshot, keeping what was already received and the locked rate."""
    snapshot = version.snapshot
    currency = await db.get(Currency, po.currency_code)
    assert currency is not None  # noqa: S101 - the order references it by foreign key
    specs = [
        LineSpec(
            product_id=line["product_id"],
            quantity=line["quantity"],
            unit_price=Decimal(line["unit_price"]),
            tax=TaxSnapshot(
                rate_id=line["tax_rate_id"],
                name=line["tax_name"],
                percent=Decimal(line["tax_percent"]),
                inclusive=line["tax_inclusive"],
                reverse_charge=line["reverse_charge"],
            ),
        )
        for line in snapshot["lines"]
    ]
    new_items, totals = po_pricing.price_lines(specs, currency)
    received = {item.product_id: item.received_quantity for item in po.items}
    _check_received_lines(po, {item.product_id: item.quantity for item in new_items})

    po.items.clear()
    # Remove the old lines first so the new ones do not collide with them on (order, product).
    await db.flush()
    for item in new_items:
        item.received_quantity = received.get(item.product_id, 0)
    po.items = new_items
    po_pricing.apply_totals(po, totals)
    if po.exchange_rate is not None:
        await po_pricing.refresh_base_amounts(db, po)
    expected = snapshot["expected_delivery_date"]
    po.expected_delivery_date = date.fromisoformat(expected) if expected else None
    po.notes = snapshot["notes"]
    if po.delivery is not None:
        po.delivery.ordered_quantity = sum(item.quantity for item in new_items)
        po.delivery.expected_date = po.expected_delivery_date
    po.version = version.version
    version.status = AmendmentStatus.APPLIED
    version.decided_at = datetime.now(UTC)
    await record_audit_event(
        db,
        user_id=actor.id,
        action="po_amended",
        entity_type="purchase_order",
        entity_id=po.id,
        extra_data={"version": version.version, "reason": version.reason, "changes": len(version.changes)},
    )


async def get_pending_version(db: AsyncSession, version_id: int) -> PurchaseOrderVersion:
    version = await db.get(PurchaseOrderVersion, version_id)
    if version is None:
        raise _error(status.HTTP_404_NOT_FOUND, "Amendment not found")
    return version


async def decide_amendment(
    db: AsyncSession, version_id: int, actor: User, *, approve: bool, comment: str | None
) -> PurchaseOrderVersion:
    version = await get_pending_version(db, version_id)
    po = await get_purchase_order_for_update(db, version.po_id)
    creator = await db.get(User, version.created_by)
    assert creator is not None  # noqa: S101 - the column is a non-null foreign key
    subject = approval_adapters.amendment_subject(version, po, creator)
    await approval_engine.decide(db, subject, actor, approve=approve, comment=comment)
    await db.commit()
    await db.refresh(version)
    return version


async def withdraw_amendment(db: AsyncSession, version_id: int, actor: User) -> PurchaseOrderVersion:
    """The person who proposed a pending amendment takes it back."""
    version = await get_pending_version(db, version_id)
    po = await get_purchase_order_for_update(db, version.po_id)
    if version.created_by != actor.id:
        raise _error(status.HTTP_403_FORBIDDEN, "Only the person who proposed an amendment can withdraw it")
    if version.status != AmendmentStatus.PENDING_APPROVAL:
        raise _error(status.HTTP_409_CONFLICT, f"This amendment is already {version.status.value}")
    await close_pending(db, po.id, actor, reason="Withdrawn")
    await db.commit()
    await db.refresh(version)
    return version


async def close_pending(db: AsyncSession, po_id: int, actor: User, *, reason: str) -> None:
    """Close any amendment still waiting for approval (the order was cancelled, or the proposer withdrew it)."""
    for version in await list_versions(db, po_id):
        if version.status != AmendmentStatus.PENDING_APPROVAL:
            continue
        await approval_engine.skip_open_steps(db, ApprovalDocumentType.PURCHASE_ORDER_AMENDMENT, version.id)
        version.status = AmendmentStatus.REJECTED
        version.decided_at = datetime.now(UTC)
        await record_audit_event(
            db,
            user_id=actor.id,
            action="po_amendment_closed",
            entity_type="purchase_order",
            entity_id=po_id,
            extra_data={"version": version.version, "reason": reason},
        )
