from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession, require_permission
from app.core.pagination import paginate
from app.models.enums import POStatus
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.supplier import Supplier
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderRead,
    PurchaseOrderUpdate,
    ReceivePurchaseOrderRequest,
)
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
    status_filter: POStatus | None = Query(default=None, alias="status"),
    supplier_id: int | None = None,
) -> PaginatedResponse[PurchaseOrderRead]:
    stmt = select(PurchaseOrder).options(*po_service.PO_LOAD_OPTIONS).order_by(PurchaseOrder.created_at.desc())
    if status_filter is not None:
        stmt = stmt.where(PurchaseOrder.status == status_filter)
    if supplier_id is not None:
        stmt = stmt.where(PurchaseOrder.supplier_id == supplier_id)

    items, total, total_pages = await paginate(db, stmt, page, page_size)
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)


@router.get("/{po_id}", response_model=PurchaseOrderRead)
async def get_purchase_order(po_id: int, db: DbSession, _: CurrentUser) -> PurchaseOrder:
    return await _get_po_or_404(db, po_id)


@router.post("", response_model=PurchaseOrderRead, status_code=status.HTTP_201_CREATED)
async def create_purchase_order(
    payload: PurchaseOrderCreate, db: DbSession, current_user: RequirePOCreate
) -> PurchaseOrder:
    supplier = await db.get(Supplier, payload.supplier_id)
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Supplier not found")

    product_ids = {item.product_id for item in payload.items}
    result = await db.execute(select(Product.id).where(Product.id.in_(product_ids)))
    found_ids = set(result.scalars().all())
    missing = product_ids - found_ids
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown product ids: {sorted(missing)}"
        )

    po = PurchaseOrder(
        po_number=await po_service.generate_po_number(db),
        supplier_id=payload.supplier_id,
        expected_delivery_date=payload.expected_delivery_date,
        notes=payload.notes,
        created_by=current_user.id,
        status=POStatus.DRAFT,
    )
    po.items = [
        PurchaseOrderItem(product_id=item.product_id, quantity=item.quantity, unit_price=item.unit_price)
        for item in payload.items
    ]
    db.add(po)
    await db.flush()
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
    if po.status != POStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft purchase orders can be edited")

    update_data = payload.model_dump(exclude_unset=True)
    items_data = update_data.pop("items", None)
    for field, value in update_data.items():
        setattr(po, field, value)

    if items_data is not None:
        product_ids = {item["product_id"] for item in items_data}
        result = await db.execute(select(Product.id).where(Product.id.in_(product_ids)))
        found_ids = set(result.scalars().all())
        missing = product_ids - found_ids
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown product ids: {sorted(missing)}"
            )

        po.items.clear()
        po.items = [
            PurchaseOrderItem(
                product_id=item["product_id"], quantity=item["quantity"], unit_price=item["unit_price"]
            )
            for item in items_data
        ]

    await record_audit_event(
        db, user_id=current_user.id, action="po_updated", entity_type="purchase_order", entity_id=po.id
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
    po_service.approve_purchase_order(po, current_user)
    await record_audit_event(
        db, user_id=current_user.id, action="po_approved", entity_type="purchase_order", entity_id=po.id
    )
    await db.commit()
    return await _get_po_or_404(db, po_id)


@router.post("/{po_id}/order", response_model=PurchaseOrderRead)
async def mark_purchase_order_ordered(
    po_id: int, db: DbSession, current_user: RequirePOTransition
) -> PurchaseOrder:
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
