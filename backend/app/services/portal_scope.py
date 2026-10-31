"""The supplier portal's single scoped query layer.

Every portal read and write goes through ``PortalScope``. It is built from the signed-in supplier account and takes
its supplier id from that account, never from the request, and every query below filters by it. A record of another
supplier is therefore indistinguishable from one that does not exist: it answers 404, so ids cannot be probed.
"""

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import DbSession, PortalUser
from app.core.file_types import DOCUMENT_KINDS
from app.core.pagination import paginate_mapped
from app.models.attachment import Attachment
from app.models.enums import AttachmentParentType, InvoiceStatus, POStatus
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.supplier import Supplier
from app.models.supplier_document import SupplierDocument
from app.models.supplier_invoice import SupplierInvoice
from app.models.user import User
from app.schemas.attachment import AttachmentRead
from app.schemas.common import PaginatedResponse
from app.schemas.portal import (
    PortalInvoiceCreate,
    PortalInvoiceRead,
    PortalMe,
    PortalOrderLine,
    PortalOrderRead,
    PortalOrderSummary,
    PortalSupplier,
)
from app.schemas.supplier_document import SupplierDocumentRead
from app.schemas.supplier_invoice import InvoiceCreate, InvoiceLineWrite
from app.services import attachment_service, invoice_service, supplier_document_service
from app.services.audit_service import record_audit_event
from app.services.supplier_document_service import DocumentUpload
from app.storage import StorageBackend, StoredObjectNotFoundError

# Suppliers see orders once they have been placed with them: never drafts, requests for approval or cancelled ones.
PORTAL_PO_STATUSES = (POStatus.ORDERED, POStatus.PARTIALLY_RECEIVED, POStatus.RECEIVED)


def _not_found(what: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{what} not found")


def _order_summary(po: PurchaseOrder) -> PortalOrderSummary:
    return PortalOrderSummary(
        id=po.id,
        po_number=po.po_number,
        status=po.status,
        currency_code=po.currency_code,
        subtotal=po.subtotal,
        tax_total=po.tax_total,
        grand_total=po.grand_total,
        expected_delivery_date=po.expected_delivery_date,
        version=po.version,
        created_at=po.created_at,
        acknowledged_at=po.acknowledged_at,
    )


def _order_line(item: PurchaseOrderItem) -> PortalOrderLine:
    return PortalOrderLine(
        product_id=item.product_id,
        product_name=item.product.name,
        sku=item.product.sku,
        quantity=item.quantity,
        received_quantity=item.received_quantity,
        unit_price=item.unit_price,
        tax_name=item.tax_name,
        tax_percent=item.tax_percent,
        line_net=item.line_net,
        line_tax=item.line_tax,
        line_total=item.line_total,
    )


def _order_read(po: PurchaseOrder) -> PortalOrderRead:
    return PortalOrderRead(**_order_summary(po).model_dump(), items=[_order_line(item) for item in po.items])


def _invoice_read(invoice: SupplierInvoice) -> PortalInvoiceRead:
    return PortalInvoiceRead(
        id=invoice.id,
        invoice_number=invoice.invoice_number,
        po_id=invoice.po_id,
        po_number=invoice.purchase_order.po_number,
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        currency_code=invoice.currency_code,
        subtotal=invoice.subtotal,
        tax_total=invoice.tax_total,
        grand_total=invoice.grand_total,
        paid_total=invoice.paid_total,
        open_amount=invoice.open_amount,
        status=invoice.status,
        created_at=invoice.created_at,
    )


class PortalScope:
    def __init__(self, db: AsyncSession, user: User, supplier: Supplier) -> None:
        self.db = db
        self.user = user
        self.supplier = supplier
        self.supplier_id = supplier.id

    def me(self) -> PortalMe:
        return PortalMe(
            id=self.user.id,
            email=self.user.email,
            full_name=self.user.full_name,
            supplier=PortalSupplier(id=self.supplier.id, name=self.supplier.name),
        )

    # Orders

    def _orders(self) -> Select[tuple[PurchaseOrder]]:
        return (
            select(PurchaseOrder)
            .options(selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.product))
            .where(PurchaseOrder.supplier_id == self.supplier_id, PurchaseOrder.status.in_(PORTAL_PO_STATUSES))
        )

    async def list_orders(
        self, status_filter: POStatus | None, page: int, page_size: int
    ) -> PaginatedResponse[PortalOrderSummary]:
        stmt = self._orders().order_by(PurchaseOrder.id.desc())
        if status_filter is not None:
            stmt = stmt.where(PurchaseOrder.status == status_filter)
        return await paginate_mapped(self.db, stmt, page, page_size, _order_summary)

    async def _order(self, po_id: int) -> PurchaseOrder:
        po = await self.db.scalar(
            self._orders().where(PurchaseOrder.id == po_id).execution_options(populate_existing=True)
        )
        if po is None:
            raise _not_found("Order")
        return po

    async def get_order(self, po_id: int) -> PortalOrderRead:
        return _order_read(await self._order(po_id))

    async def acknowledge_order(self, po_id: int) -> PortalOrderRead:
        """Confirm the order. Doing it again changes nothing: the first acknowledgement stands."""
        po = await self._order(po_id)
        if po.acknowledged_at is None:
            # The WHERE clause makes this the single winner when two requests race.
            claimed = await self.db.execute(
                update(PurchaseOrder)
                .where(
                    PurchaseOrder.id == po.id,
                    PurchaseOrder.supplier_id == self.supplier_id,
                    PurchaseOrder.acknowledged_at.is_(None),
                )
                .values(acknowledged_at=datetime.now(UTC), acknowledged_by=self.user.id)
            )
            if claimed.rowcount:
                await record_audit_event(
                    self.db,
                    user_id=self.user.id,
                    action="po_acknowledged",
                    entity_type="purchase_order",
                    entity_id=po.id,
                    extra_data={"po_number": po.po_number, "version": po.version},
                )
            await self.db.commit()
        return _order_read(await self._order(po_id))

    # Invoices

    def _invoices(self) -> Select[tuple[SupplierInvoice]]:
        return (
            select(SupplierInvoice)
            .options(selectinload(SupplierInvoice.purchase_order))
            .where(SupplierInvoice.supplier_id == self.supplier_id)
        )

    async def list_invoices(
        self, status_filter: InvoiceStatus | None, page: int, page_size: int
    ) -> PaginatedResponse[PortalInvoiceRead]:
        stmt = self._invoices().order_by(SupplierInvoice.id.desc())
        if status_filter is not None:
            stmt = stmt.where(SupplierInvoice.status == status_filter)
        return await paginate_mapped(self.db, stmt, page, page_size, _invoice_read)

    async def _invoice(self, invoice_id: int) -> SupplierInvoice:
        invoice = await self.db.scalar(
            self._invoices().where(SupplierInvoice.id == invoice_id).execution_options(populate_existing=True)
        )
        if invoice is None:
            raise _not_found("Invoice")
        return invoice

    async def get_invoice(self, invoice_id: int) -> PortalInvoiceRead:
        return _invoice_read(await self._invoice(invoice_id))

    async def create_invoice(self, payload: PortalInvoiceCreate) -> PortalInvoiceRead:
        """A draft invoice against one of the supplier's own orders. Finance reviews and submits it for matching."""
        order = await self._order(payload.po_id)
        await self._ensure_number_is_new(payload.invoice_number)
        on_order = {item.product_id for item in order.items}
        for position, line in enumerate(payload.lines, start=1):
            if line.product_id is not None and line.product_id not in on_order:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Line {position} is for a product that is not on order {order.po_number}",
                )
        # Supplier, currency and tax are never taken from the supplier: they come from the order.
        body = InvoiceCreate(
            po_id=order.id,
            invoice_number=payload.invoice_number,
            invoice_date=payload.invoice_date,
            due_date=payload.due_date,
            notes=payload.notes,
            lines=[
                InvoiceLineWrite(
                    product_id=line.product_id,
                    description=line.description,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                )
                for line in payload.lines
            ],
        )
        invoice = await invoice_service.create_invoice(self.db, body, self.user)
        return await self.get_invoice(invoice.id)

    async def _ensure_number_is_new(self, number: str) -> None:
        wanted = number.strip().lower()
        taken = await self.db.scalar(
            select(func.count())
            .select_from(SupplierInvoice)
            .where(
                SupplierInvoice.supplier_id == self.supplier_id,
                SupplierInvoice.status != InvoiceStatus.VOID,
                func.lower(func.trim(SupplierInvoice.invoice_number)) == wanted,
            )
        )
        if taken:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=f"You have already sent an invoice numbered {number}"
            )

    async def attach_to_invoice(
        self, storage: StorageBackend, invoice_id: int, filename: str | None, data: bytes
    ) -> AttachmentRead:
        invoice = await self._invoice(invoice_id)
        if invoice.status != InvoiceStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Files can only be added while the invoice is a draft"
            )
        return await attachment_service.store_attachment(
            self.db,
            storage,
            self.user,
            AttachmentParentType.SUPPLIER_INVOICE,
            invoice.id,
            filename,
            data,
            DOCUMENT_KINDS,
        )

    async def _attachments(self, invoice_id: int) -> list[Attachment]:
        invoice = await self._invoice(invoice_id)
        rows = await self.db.execute(
            select(Attachment)
            .where(Attachment.parent_type == AttachmentParentType.SUPPLIER_INVOICE, Attachment.parent_id == invoice.id)
            .order_by(Attachment.id)
        )
        return list(rows.scalars().all())

    async def list_invoice_files(self, invoice_id: int) -> list[AttachmentRead]:
        result = []
        for attachment in await self._attachments(invoice_id):
            uploader = await self.db.get(User, attachment.uploaded_by)
            assert uploader is not None  # noqa: S101 - the column is a non-null foreign key
            result.append(attachment_service.to_read(attachment, uploader))
        return result

    async def read_invoice_file(
        self, storage: StorageBackend, invoice_id: int, attachment_id: int
    ) -> tuple[Attachment, bytes]:
        attachment = next((row for row in await self._attachments(invoice_id) if row.id == attachment_id), None)
        if attachment is None:
            raise _not_found("File")
        try:
            return attachment, await storage.read(attachment.storage_key)
        except StoredObjectNotFoundError as exc:
            raise _not_found("File") from exc

    # Documents: the same service the internal screens use, always for this supplier.

    async def list_documents(self, today: date) -> list[SupplierDocumentRead]:
        return await supplier_document_service.list_documents(self.db, self.supplier_id, today)

    async def upload_document(
        self, storage: StorageBackend, upload: DocumentUpload, today: date
    ) -> SupplierDocumentRead:
        return await supplier_document_service.upload_document(
            self.db, storage, self.user, self.supplier_id, upload, today
        )

    async def read_document(self, storage: StorageBackend, document_id: int) -> tuple[SupplierDocument, bytes]:
        return await supplier_document_service.read_document_file(self.db, storage, self.supplier_id, document_id)

    async def delete_document(self, storage: StorageBackend, document_id: int) -> None:
        await supplier_document_service.delete_document(self.db, storage, self.user, self.supplier_id, document_id)


async def get_portal_scope(db: DbSession, user: PortalUser) -> PortalScope:
    """The scope of the signed-in supplier account. A deactivated supplier locks its accounts out of the portal."""
    supplier = await db.get(Supplier, user.supplier_id) if user.supplier_id is not None else None
    if supplier is None or not supplier.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This supplier account is not active")
    return PortalScope(db, user, supplier)


Portal = Annotated[PortalScope, Depends(get_portal_scope)]
