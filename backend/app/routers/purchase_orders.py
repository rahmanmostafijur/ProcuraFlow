from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession, require_permission
from app.core.pagination import paginate
from app.models.enums import POStatus
from app.models.purchase_order import PurchaseOrder
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderRead,
    PurchaseOrderUpdate,
    ReceivePurchaseOrderRequest,
)
from app.services import po_draft_service
from app.services import purchase_order_service as po_service
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])

RequirePOCreate = Annotated[User, Depends(require_permission("po:create"))]
RequirePOApprove = Annotated[User, Depends(require_permission("po:approve"))]
RequirePOTransition = Annotated[User, Depends(require_permission("po:transition"))]
RequireInventoryWrite = Annotated[User, Depends(require_permission("inventory:write"))]


async def _get_po_or_404(db: DbSession, po_id: int) -> PurchaseOrder:
    result = await db.execute(
        select(PurchaseOrder).options(*po_service.PO_LOAD_OPTIONS).where(PurchaseOrder.id == po_id)
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
    po_service.submit_purchase_order(po)
    await record_audit_event(
        db, user_id=current_user.id, action="po_submitted", entity_type="purchase_order", entity_id=po.id
    )
    await db.commit()
    return await _get_po_or_404(db, po_id)


@router.post("/{po_id}/approve", response_model=PurchaseOrderRead)
async def approve_purchase_order(po_id: int, db: DbSession, current_user: RequirePOApprove) -> PurchaseOrder:
    po = await po_service.get_purchase_order_for_update(db, po_id)
    await po_service.approve_purchase_order(db, po, current_user)
    await record_audit_event(
        db, user_id=current_user.id, action="po_approved", entity_type="purchase_order", entity_id=po.id
    )
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
    await record_audit_event(
        db, user_id=current_user.id, action="po_cancelled", entity_type="purchase_order", entity_id=po.id
    )
    await db.commit()
    return await _get_po_or_404(db, po_id)


@router.post("/{po_id}/receive", response_model=PurchaseOrderRead)
async def receive_purchase_order(
    po_id: int, payload: ReceivePurchaseOrderRequest, db: DbSession, current_user: RequireInventoryWrite
) -> PurchaseOrder:
    po = await po_service.get_purchase_order_for_update(db, po_id)
    received_items = {item.product_id: item.quantity for item in payload.items}
    await po_service.receive_purchase_order_items(db, po, received_items, current_user.id)
    await record_audit_event(
        db,
        user_id=current_user.id,
        action="po_received",
        entity_type="purchase_order",
        entity_id=po.id,
        extra_data={"items": received_items},
    )
    await db.commit()
    return await _get_po_or_404(db, po_id)
