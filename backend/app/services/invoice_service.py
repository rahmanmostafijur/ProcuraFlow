"""Recording and editing supplier invoices against purchase orders, and listing them with their totals."""

from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.pagination import paginate_mapped
from app.models.currency import Currency
from app.models.enums import InvoiceStatus, POStatus
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice
from app.models.user import User
from app.schemas.supplier_invoice import (
    InvoiceCreate,
    InvoiceLineWrite,
    InvoiceListResponse,
    InvoiceListTotals,
    InvoiceSummary,
    InvoiceUpdate,
)
from app.services import invoice_access, invoice_pricing, metrics_service, po_pricing
from app.services.audit_service import current_values, field_changes, record_audit_event
from app.services.company_settings_service import get_company_settings
from app.services.invoice_pricing import InvoiceLineSpec
from app.services.invoice_queries import InvoiceFilter, get_invoice, list_statement

# Invoices are recorded against orders that have been placed with the supplier.
INVOICEABLE_PO_STATUSES = (POStatus.ORDERED, POStatus.PARTIALLY_RECEIVED, POStatus.RECEIVED)
UNPROCESSABLE = status.HTTP_422_UNPROCESSABLE_CONTENT


def _error(code: int, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail=message)


async def load_purchase_order(db: AsyncSession, po_id: int) -> PurchaseOrder:
    po = await db.scalar(
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.items), selectinload(PurchaseOrder.supplier))
        .where(PurchaseOrder.id == po_id)
        .execution_options(populate_existing=True)
    )
    if po is None:
        raise _error(status.HTTP_400_BAD_REQUEST, "Purchase order not found")
    return po


def ensure_po_is_invoiceable(po: PurchaseOrder) -> None:
    if po.status not in INVOICEABLE_PO_STATUSES:
        raise _error(
            status.HTTP_409_CONFLICT,
            f"Invoices can only be recorded against orders that are ordered or received; "
            f"{po.po_number} is '{po.status.value}'.",
        )


async def default_due_date(db: AsyncSession, supplier: Supplier, invoice_date: date) -> date:
    """Invoice date plus the supplier's payment terms, else the company's default terms."""
    days = supplier.payment_terms_days
    if days is None:
        days = (await get_company_settings(db)).default_payment_terms_days
    return invoice_date + timedelta(days=days)


async def _line_specs(db: AsyncSession, po: PurchaseOrder, lines: list[InvoiceLineWrite]) -> list[InvoiceLineSpec]:
    product_ids = {line.product_id for line in lines if line.product_id is not None}
    names: dict[int, str] = {}
    if product_ids:
        rows = (await db.execute(select(Product.id, Product.name).where(Product.id.in_(product_ids)))).all()
        names = {row.id: row.name for row in rows}
        missing = sorted(product_ids - names.keys())
        if missing:
            raise _error(status.HTTP_400_BAD_REQUEST, f"Unknown product ids: {missing}")
    snapshots = await po_pricing.resolve_tax_snapshots(
        db, (line.tax_rate_id for line in lines if line.tax_rate_id is not None)
    )
    item_by_product = {item.product_id: item for item in po.items}
    order_tax = {spec.product_id: spec.tax for spec in po_pricing.specs_from_items(po.items)}

    specs: list[InvoiceLineSpec] = []
    for position, line in enumerate(lines, start=1):
        description = line.description or (names.get(line.product_id) if line.product_id is not None else None)
        if description is None:
            raise _error(UNPROCESSABLE, f"Line {position} needs a description or a product")
        if "tax_rate_id" in line.model_fields_set:
            tax = snapshots[line.tax_rate_id] if line.tax_rate_id is not None else invoice_pricing.NO_TAX
        else:
            tax = (
                order_tax.get(line.product_id, invoice_pricing.NO_TAX)
                if line.product_id is not None
                else invoice_pricing.NO_TAX
            )
        item = item_by_product.get(line.product_id) if line.product_id is not None else None
        specs.append(
            InvoiceLineSpec(
                product_id=line.product_id,
                po_item_id=item.id if item else None,
                description=description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                tax=tax,
            )
        )
    return specs


def _ensure_dates_in_order(invoice_date: date, due_date: date) -> None:
    if due_date < invoice_date:
        raise _error(UNPROCESSABLE, "The due date cannot be before the invoice date")


async def create_invoice(db: AsyncSession, payload: InvoiceCreate, actor: User) -> SupplierInvoice:
    po = await load_purchase_order(db, payload.po_id)
    ensure_po_is_invoiceable(po)
    if payload.supplier_id is not None and payload.supplier_id != po.supplier_id:
        raise _error(UNPROCESSABLE, f"Purchase order {po.po_number} belongs to a different supplier")
    if payload.currency_code is not None and payload.currency_code != po.currency_code:
        raise _error(
            UNPROCESSABLE,
            f"The invoice currency {payload.currency_code} must equal the purchase order currency {po.currency_code}",
        )
    currency = await db.get(Currency, po.currency_code)
    assert currency is not None  # noqa: S101 - the order references it by foreign key
    due_date = payload.due_date or await default_due_date(db, po.supplier, payload.invoice_date)
    _ensure_dates_in_order(payload.invoice_date, due_date)

    lines, totals = invoice_pricing.price_lines(await _line_specs(db, po, payload.lines), currency)
    invoice = SupplierInvoice(
        supplier_id=po.supplier_id,
        po_id=po.id,
        invoice_number=payload.invoice_number,
        invoice_date=payload.invoice_date,
        due_date=due_date,
        currency_code=po.currency_code,
        notes=payload.notes,
        created_by=actor.id,
    )
    invoice.lines = lines
    invoice_pricing.apply_totals(invoice, totals)
    db.add(invoice)
    await db.flush()
    await record_audit_event(
        db,
        user_id=actor.id,
        action="invoice_created",
        entity_type="supplier_invoice",
        entity_id=invoice.id,
        extra_data={
            "po_id": po.id,
            "invoice_number": invoice.invoice_number,
            "grand_total": str(invoice.grand_total),
            "currency": invoice.currency_code,
        },
    )
    await db.commit()
    return await get_invoice(db, invoice.id)


async def update_invoice(db: AsyncSession, invoice_id: int, payload: InvoiceUpdate, actor: User) -> SupplierInvoice:
    invoice, actor = await invoice_access.load_for(db, invoice_id, actor, for_update=True)
    invoice_access.ensure_can_modify(invoice, actor)
    if invoice.status != InvoiceStatus.DRAFT:
        raise _error(
            status.HTTP_409_CONFLICT, f"Only draft invoices can be edited; this one is '{invoice.status.value}'"
        )

    changes = payload.model_dump(exclude_unset=True, exclude={"lines"})
    for field in ("invoice_number", "invoice_date", "due_date"):
        if field in changes and changes[field] is None:
            raise _error(UNPROCESSABLE, f"'{field}' cannot be empty")
    audit = field_changes(current_values(invoice, changes), changes)
    new_date = changes.get("invoice_date", invoice.invoice_date)
    if "due_date" not in changes and new_date != invoice.invoice_date:
        # The date moved and the due date was not given: the terms apply to the new date.
        po = await load_purchase_order(db, invoice.po_id)
        changes["due_date"] = await default_due_date(db, po.supplier, new_date)
    _ensure_dates_in_order(new_date, changes.get("due_date", invoice.due_date))
    for field, value in changes.items():
        setattr(invoice, field, value)

    if payload.lines is not None:
        po = await load_purchase_order(db, invoice.po_id)
        currency = await db.get(Currency, invoice.currency_code)
        assert currency is not None  # noqa: S101 - the invoice references it by foreign key
        lines, totals = invoice_pricing.price_lines(await _line_specs(db, po, payload.lines), currency)
        invoice.lines.clear()
        # Remove the old lines first, like purchase orders do when their lines are replaced.
        await db.flush()
        invoice.lines = lines
        invoice_pricing.apply_totals(invoice, totals)
        audit["lines"] = {"replaced": len(lines)}
    await record_audit_event(
        db,
        user_id=actor.id,
        action="invoice_updated",
        entity_type="supplier_invoice",
        entity_id=invoice.id,
        extra_data={"changes": audit},
    )
    await db.commit()
    return await get_invoice(db, invoice_id)


async def read_invoice(db: AsyncSession, invoice_id: int, viewer: User) -> SupplierInvoice:
    """The invoice if the viewer may see it; otherwise the same 404 as a missing one."""
    invoice, viewer = await invoice_access.load_for(db, invoice_id, viewer)
    if not await invoice_access.can_view(db, invoice, viewer):
        raise invoice_access.not_found()
    return invoice


async def list_invoices(db: AsyncSession, flt: InvoiceFilter, page: int, page_size: int) -> InvoiceListResponse:
    """One page of invoices plus totals for everything the filters match, from the shared metric functions."""
    context = await metrics_service.get_context(db)
    paged = await paginate_mapped(
        db, list_statement(flt), page, page_size, lambda row: InvoiceSummary.model_validate(row, from_attributes=True)
    )
    by_status = await metrics_service.invoice_counts_by_status(db, flt)
    totals = InvoiceListTotals(
        by_status=by_status,
        needing_attention=metrics_service.needing_attention_from(by_status),
        payables_outstanding=await metrics_service.payables_outstanding(db, context, flt),
        payables_overdue=await metrics_service.payables_overdue(db, context, flt),
    )
    return InvoiceListResponse(
        items=paged.items,
        total=paged.total,
        page=paged.page,
        page_size=paged.page_size,
        total_pages=paged.total_pages,
        totals=totals,
    )
