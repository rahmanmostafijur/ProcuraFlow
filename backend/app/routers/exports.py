from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.core.deps import DbSession, require_permission
from app.models.user import User
from app.services.accounting_exports import QUICKBOOKS_BILLS, XERO_BILLS
from app.services.audit_service import record_audit_event
from app.services.export_common import Dataset, ExportFilters, validate_filters
from app.services.export_writer import csv_chunks
from app.services.record_exports import INVOICES, PURCHASE_ORDERS, SUPPLIERS

router = APIRouter(prefix="/exports", tags=["exports"])

RequireExport = Annotated[User, Depends(require_permission("export:read"))]
DateFrom = Annotated[date | None, Query(description="First day to include (inclusive)")]
DateTo = Annotated[date | None, Query(description="Last day to include (inclusive)")]
StatusFilter = Annotated[str | None, Query(description="Only rows in this status")]


async def _export(db: DbSession, user: User, dataset: Dataset, filters: ExportFilters) -> StreamingResponse:
    validate_filters(dataset, filters)
    # Recorded and committed before the first byte is sent: the download cannot happen without its audit entry.
    await record_audit_event(
        db,
        user_id=user.id,
        action="export_downloaded",
        entity_type="export",
        extra_data={"dataset": dataset.name} | filters.as_audit(),
    )
    await db.commit()
    return StreamingResponse(
        csv_chunks(dataset.header, dataset.rows(db, filters), dataset.date_format),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{dataset.filename}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/bills/quickbooks.csv")
async def quickbooks_bills(
    db: DbSession, user: RequireExport, date_from: DateFrom = None, date_to: DateTo = None, status: StatusFilter = None
) -> StreamingResponse:
    """Approved and paid supplier invoices in the QuickBooks Online bill import layout."""
    return await _export(db, user, QUICKBOOKS_BILLS, ExportFilters(date_from, date_to, status))


@router.get("/bills/xero.csv")
async def xero_bills(
    db: DbSession, user: RequireExport, date_from: DateFrom = None, date_to: DateTo = None, status: StatusFilter = None
) -> StreamingResponse:
    """Approved and paid supplier invoices in the Xero bill import layout."""
    return await _export(db, user, XERO_BILLS, ExportFilters(date_from, date_to, status))


@router.get("/purchase-orders.csv")
async def purchase_orders_csv(
    db: DbSession, user: RequireExport, date_from: DateFrom = None, date_to: DateTo = None, status: StatusFilter = None
) -> StreamingResponse:
    return await _export(db, user, PURCHASE_ORDERS, ExportFilters(date_from, date_to, status))


@router.get("/invoices.csv")
async def invoices_csv(
    db: DbSession, user: RequireExport, date_from: DateFrom = None, date_to: DateTo = None, status: StatusFilter = None
) -> StreamingResponse:
    return await _export(db, user, INVOICES, ExportFilters(date_from, date_to, status))


@router.get("/suppliers.csv")
async def suppliers_csv(
    db: DbSession, user: RequireExport, date_from: DateFrom = None, date_to: DateTo = None, status: StatusFilter = None
) -> StreamingResponse:
    return await _export(db, user, SUPPLIERS, ExportFilters(date_from, date_to, status))
