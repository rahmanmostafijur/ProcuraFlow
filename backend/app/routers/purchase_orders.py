from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession, require_permission
from app.core.pagination import paginate
from app.models.enums import ApprovalDocumentType, POStatus
from app.models.goods_receipt import GoodsReceipt
from app.models.purchase_order import PurchaseOrder
from app.models.user import User
from app.schemas.approval import DecisionRequest, RejectionRequest
from app.schemas.common import PaginatedResponse
from app.schemas.goods_receipt import GoodsReceiptRead
from app.schemas.po_version import PurchaseOrderAmend, PurchaseOrderVersionRead
from app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderRead,
    PurchaseOrderUpdate,
    ReceivePurchaseOrderRequest,
)
from app.services import approval_engine, po_amendment_service, po_draft_service
from app.services import purchase_order_service as po_service
from app.services.audit_service import record_audit_event
from app.services.company_settings_service import get_company_settings
from app.services.email_service import queue_email
from app.services.goods_receipt_service import ReceiptInput, receive_goods
from app.services.goods_receipt_service import list_receipts as list_goods_receipts
from app.services.po_document_service import render_purchase_order_pdf
from app.services.po_version_reads import to_version_read, to_version_reads
from app.storage import StorageBackend, get_storage

router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])

RequirePOCreate = Annotated[User, Depends(require_permission("po:create"))]
RequirePOTransition = Annotated[User, Depends(require_permission("po:transition"))]
RequireInventoryWrite = Annotated[User, Depends(require_permission("inventory:write"))]
Storage = Annotated[StorageBackend, Depends(get_storage)]


async def _get_po_or_404(db: DbSession, po_id: int) -> PurchaseOrder:
    result = await db.execute(
        select(PurchaseOrder)
        .options(*po_service.PO_LOAD_OPTIONS)
        .where(PurchaseOrder.id == po_id)
        # Reflect what was just committed, not objects this request loaded before the change.
        .execution_options(populate_existing=True)
    )
    po = result.scalar_one_or_none()
    if po is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
    return po


@router.get("", response_model=PaginatedResponse[PurchaseOrderRead])
async def list_purchase_orders(
    db: DbSession,
    _: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Annotated[POStatus | None, Query(alias="status")] = None,
    supplier_id: int | None = None,
) -> PaginatedResponse[PurchaseOrderRead]:
    stmt = select(PurchaseOrder).options(*po_service.PO_LOAD_OPTIONS).order_by(PurchaseOrder.created_at.desc())
    if status_filter is not None:
        stmt = stmt.where(PurchaseOrder.status == status_filter)
    if supplier_id is not None:
        stmt = stmt.where(PurchaseOrder.supplier_id == supplier_id)

    return await paginate(db, stmt, page, page_size, PurchaseOrderRead)


@router.get("/{po_id}", response_model=PurchaseOrderRead)
async def get_purchase_order(po_id: int, db: DbSession, _: CurrentUser) -> PurchaseOrder:
    return await _get_po_or_404(db, po_id)


@router.post("", response_model=PurchaseOrderRead, status_code=status.HTTP_201_CREATED)
async def create_purchase_order(
    payload: PurchaseOrderCreate, db: DbSession, current_user: RequirePOCreate
) -> PurchaseOrder:
    po = await po_draft_service.create_draft(db, payload, current_user)
    await record_audit_event(
        db, user_id=current_user.id, action="po_created", entity_type="purchase_order", entity_id=po.id
    )
    await db.commit()
    return await _get_po_or_404(db, po.id)


@router.patch("/{po_id}", response_model=PurchaseOrderRead)
async def update_purchase_order(
    po_id: int, payload: PurchaseOrderUpdate, db: DbSession, current_user: RequirePOCreate
) -> PurchaseOrder:
    po = await po_service.get_purchase_order_for_update(db, po_id)
    changes = await po_draft_service.update_draft(db, po, payload)
    await record_audit_event(
        db,
        user_id=current_user.id,
        action="po_updated",
        entity_type="purchase_order",
        entity_id=po.id,
        extra_data={"changes": changes},
    )
    await db.commit()
    return await _get_po_or_404(db, po_id)


@router.post("/{po_id}/submit", response_model=PurchaseOrderRead)
async def submit_purchase_order(po_id: int, db: DbSession, current_user: RequirePOCreate) -> PurchaseOrder:
    po = await po_service.get_purchase_order_for_update(db, po_id)
    await po_service.submit_purchase_order(db, po)
    await record_audit_event(
        db, user_id=current_user.id, action="po_submitted", entity_type="purchase_order", entity_id=po.id
    )
    await db.commit()
    return await _get_po_or_404(db, po_id)


@router.post("/{po_id}/approve", response_model=PurchaseOrderRead)
async def approve_purchase_order(
    po_id: int, db: DbSession, current_user: CurrentUser, payload: DecisionRequest | None = None
) -> PurchaseOrder:
    """Decide the order's current approval step; the last step approves it.

    Who may decide is the approval engine's call (role, limits, delegation, budget), so any signed-in user may try
    and gets a 403 saying why when they may not.
    """
    po = await po_service.get_purchase_order_for_update(db, po_id)
    await po_service.decide_purchase_order(
        db, po, current_user, approve=True, comment=payload.comment if payload else None
    )
    await db.commit()
    return await _get_po_or_404(db, po_id)


@router.post("/{po_id}/reject", response_model=PurchaseOrderRead)
async def reject_purchase_order(
    po_id: int, payload: RejectionRequest, db: DbSession, current_user: CurrentUser
) -> PurchaseOrder:
    """Reject the order at its current step: the order is cancelled and the reason is kept."""
    po = await po_service.get_purchase_order_for_update(db, po_id)
    await po_service.decide_purchase_order(db, po, current_user, approve=False, comment=payload.comment)
    await db.commit()
    return await _get_po_or_404(db, po_id)


@router.post("/{po_id}/order", response_model=PurchaseOrderRead)
async def mark_purchase_order_ordered(po_id: int, db: DbSession, current_user: RequirePOTransition) -> PurchaseOrder:
    po = await po_service.get_purchase_order_for_update(db, po_id)
    po_service.mark_purchase_order_ordered(db, po)
    await record_audit_event(
        db, user_id=current_user.id, action="po_ordered", entity_type="purchase_order", entity_id=po.id
    )
    await db.commit()
    return await _get_po_or_404(db, po_id)


@router.post("/{po_id}/cancel", response_model=PurchaseOrderRead)
async def cancel_purchase_order(po_id: int, db: DbSession, current_user: RequirePOTransition) -> PurchaseOrder:
    po = await po_service.get_purchase_order_for_update(db, po_id)
    po_service.cancel_purchase_order(po)
    # Nothing left to approve on a cancelled order, including an amendment that was waiting.
    await approval_engine.skip_open_steps(db, ApprovalDocumentType.PURCHASE_ORDER, po.id)
    await po_amendment_service.close_pending(db, po.id, current_user, reason="Order cancelled")
    await record_audit_event(
        db, user_id=current_user.id, action="po_cancelled", entity_type="purchase_order", entity_id=po.id
    )
    await db.commit()
    return await _get_po_or_404(db, po_id)


@router.get("/{po_id}/pdf")
async def download_purchase_order_pdf(po_id: int, db: DbSession, storage: Storage, _: CurrentUser) -> Response:
    po = await _get_po_or_404(db, po_id)
    pdf = await render_purchase_order_pdf(db, storage, po)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{po.po_number}.pdf"'},
    )


@router.post("/{po_id}/send", status_code=status.HTTP_202_ACCEPTED)
async def send_purchase_order_to_supplier(
    po_id: int, db: DbSession, current_user: RequirePOTransition
) -> dict[str, str]:
    """Queue the order email to the supplier. Only an ordered purchase order can be sent."""
    po = await _get_po_or_404(db, po_id)
    if po.status != POStatus.ORDERED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only an ordered purchase order can be sent")
    if not po.supplier.email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="The supplier has no email address"
        )
    company = await get_company_settings(db)
    await queue_email(
        db,
        po.supplier.email,
        "po_to_supplier",
        {
            "supplier_name": po.supplier.name,
            "po_number": po.po_number,
            "company_name": company.company_name,
            "total": f"{po.currency_code} {po.grand_total:,.2f}",
            "delivery_date": po.expected_delivery_date.isoformat() if po.expected_delivery_date else "to be agreed",
        },
    )
    await record_audit_event(
        db, user_id=current_user.id, action="po_sent", entity_type="purchase_order", entity_id=po.id
    )
    await db.commit()
    return {"status": "queued"}


@router.get("/{po_id}/versions", response_model=list[PurchaseOrderVersionRead])
async def list_versions(po_id: int, db: DbSession, _: CurrentUser) -> list[PurchaseOrderVersionRead]:
    """The order's amendment history, oldest first, each with a readable diff from the version before."""
    await _get_po_or_404(db, po_id)
    return await to_version_reads(db, await po_amendment_service.list_versions(db, po_id))


@router.post("/{po_id}/amend", response_model=PurchaseOrderVersionRead, status_code=status.HTTP_201_CREATED)
async def amend_purchase_order(
    po_id: int, payload: PurchaseOrderAmend, db: DbSession, current_user: RequirePOTransition
) -> PurchaseOrderVersionRead:
    """Change an order that has been placed. A change that raises the total waits for approval."""
    po = await po_service.get_purchase_order_for_update(db, po_id)
    version = await po_amendment_service.amend_purchase_order(db, po, payload, current_user)
    await db.commit()
    await db.refresh(version)
    return await to_version_read(db, version)


@router.post("/{po_id}/receive", response_model=PurchaseOrderRead)
async def receive_purchase_order(
    po_id: int, payload: ReceivePurchaseOrderRequest, db: DbSession, current_user: RequireInventoryWrite
) -> PurchaseOrder:
    """Book a delivery. Rejected units stay open on the order; only accepted units enter stock."""
    po = await po_service.get_purchase_order_for_update(db, po_id)
    lines = [
        ReceiptInput(
            product_id=item.product_id,
            delivered=item.quantity,
            rejected=item.rejected_quantity,
            condition=item.condition,
            note=item.note,
        )
        for item in payload.items
    ]
    receipt = await receive_goods(db, po, lines, current_user.id, payload.note)
    await record_audit_event(
        db,
        user_id=current_user.id,
        action="po_received",
        entity_type="purchase_order",
        entity_id=po.id,
        extra_data={
            "items": {line.product_id: line.delivered for line in lines},
            "rejected": {line.product_id: line.rejected for line in lines},
            "receipt_id": receipt.id,
        },
    )
    await db.commit()
    return await _get_po_or_404(db, po_id)


@router.get("/{po_id}/receipts", response_model=list[GoodsReceiptRead])
async def list_receipts(po_id: int, db: DbSession, _: CurrentUser) -> list[GoodsReceipt]:
    """The deliveries booked against the order, oldest first, with what was accepted and rejected on each."""
    await _get_po_or_404(db, po_id)
    return await list_goods_receipts(db, po_id)
