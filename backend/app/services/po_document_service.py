import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.currency import Currency
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.services.company_settings_service import get_company_settings
from app.services.po_pdf import DEFAULT_BRAND_COLOR, PdfLine, PdfOrder, PdfParty, render_po_pdf
from app.storage import StorageBackend, StoredObjectNotFoundError

logger = logging.getLogger(__name__)


def _address_lines(*parts: str | None) -> tuple[str, ...]:
    return tuple(part for part in parts if part)


async def build_pdf_order(db: AsyncSession, storage: StorageBackend, po: PurchaseOrder) -> PdfOrder:
    settings = await get_company_settings(db)
    currency = await db.get(Currency, po.currency_code)
    if currency is None:
        raise ValueError(f"Currency {po.currency_code} is missing")
    logo: bytes | None = None
    if settings.logo_storage_key:
        try:
            logo = await storage.read(settings.logo_storage_key)
        except StoredObjectNotFoundError:
            logger.warning("Company logo could not be read; printing without it")
    supplier = po.supplier
    items = (
        (
            await db.execute(
                select(PurchaseOrderItem)
                .options(selectinload(PurchaseOrderItem.product))
                .where(PurchaseOrderItem.po_id == po.id)
                .order_by(PurchaseOrderItem.id)
            )
        )
        .scalars()
        .all()
    )
    city_line = " ".join(part for part in (settings.postal_code, settings.city) if part)
    lines = tuple(
        PdfLine(
            sku=item.product.sku,
            description=item.product.name,
            quantity=item.quantity,
            unit_price=item.unit_price,
            tax_name=item.tax_name or "No tax",
            tax_percent=item.tax_percent,
            net=item.line_net,
            tax=item.line_tax,
            total=item.line_total,
        )
        for item in items
    )
    return PdfOrder(
        po_number=po.po_number,
        issue_date=po.created_at.date(),
        expected_delivery=po.expected_delivery_date,
        currency_code=currency.code,
        currency_symbol=currency.symbol,
        minor_units=currency.minor_units,
        payment_terms_days=supplier.payment_terms_days,
        notes=po.notes,
        company=PdfParty(
            name=settings.legal_name or settings.company_name,
            address_lines=_address_lines(
                settings.address_line1, settings.address_line2, city_line, settings.region, settings.country_code
            ),
            tax_id=settings.tax_id,
        ),
        supplier=PdfParty(
            name=supplier.name,
            address_lines=_address_lines(supplier.address, supplier.country_code),
            tax_id=supplier.tax_id,
        ),
        lines=lines,
        subtotal=po.subtotal,
        tax_total=po.tax_total,
        grand_total=po.grand_total,
        brand_color=settings.brand_color or DEFAULT_BRAND_COLOR,
        logo=logo,
    )


async def render_purchase_order_pdf(db: AsyncSession, storage: StorageBackend, po: PurchaseOrder) -> bytes:
    return render_po_pdf(await build_pdf_order(db, storage, po))
