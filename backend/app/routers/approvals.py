from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.models.enums import ApprovalDocumentType
from app.models.po_version import PurchaseOrderVersion
from app.models.purchase_order import PurchaseOrder
from app.models.supplier_invoice import SupplierInvoice
from app.schemas.approval import ApprovalTimelineStep, QueuePage
from app.services import approval_adapters  # noqa: F401 - registers the document adapters
from app.services.approval_engine import all_steps
from app.services.approval_queue_service import queue_for, timeline
from app.services.invoice_access import can_view
from app.services.purchase_request_service import get_request

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("/queue", response_model=QueuePage)
async def my_approvals(
    db: DbSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> QueuePage:
    """Everything waiting for the signed-in user's decision: requests, orders and order amendments in one list.

    The list is worked out for the caller alone, so a user can never see a document they could not decide.
    """
    items = await queue_for(db, user)
    start = (page - 1) * page_size
    return QueuePage(items=items[start : start + page_size], total=len(items))


async def _ensure_can_see(
    db: DbSession, user: CurrentUser, document_type: ApprovalDocumentType, document_id: int
) -> None:
    """Whoever can open a document can see how its approval went; anyone else is told it does not exist."""
    not_found = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if document_type == ApprovalDocumentType.PURCHASE_REQUEST:
        await get_request(db, document_id, user)  # raises 404 when the user may not see it
    elif document_type == ApprovalDocumentType.PURCHASE_ORDER:
        if await db.scalar(select(PurchaseOrder.id).where(PurchaseOrder.id == document_id)) is None:
            raise not_found
    elif document_type == ApprovalDocumentType.PURCHASE_ORDER_AMENDMENT:
        if await db.scalar(select(PurchaseOrderVersion.id).where(PurchaseOrderVersion.id == document_id)) is None:
            raise not_found
    elif document_type == ApprovalDocumentType.INVOICE_EXCEPTION:
        invoice = await db.get(SupplierInvoice, document_id)
        if invoice is None or not await can_view(db, invoice, user):
            raise not_found
    else:
        raise not_found


@router.get("/{document_type}/{document_id}/steps", response_model=list[ApprovalTimelineStep])
async def approval_history(
    document_type: ApprovalDocumentType, document_id: int, db: DbSession, user: CurrentUser
) -> list[ApprovalTimelineStep]:
    """Every approval step the document has had, oldest round first."""
    await _ensure_can_see(db, user, document_type, document_id)
    return await timeline(db, await all_steps(db, document_type, document_id))
