from decimal import Decimal

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PurchaseRequestStatus
from app.models.purchase_request import PurchaseRequest, PurchaseRequestLine
from app.models.user import User
from app.schemas.purchase_order import POItemCreate, PurchaseOrderCreate
from app.schemas.purchase_request import ConvertOrder, ConvertRequest
from app.services import po_draft_service
from app.services.audit_service import record_audit_event
from app.services.purchase_request_service import get_request


def _error(code: int, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail=message)


def _order_items(request: PurchaseRequest, order: ConvertOrder, used: set[int]) -> list[POItemCreate]:
    lines_by_id = {line.id: line for line in request.lines}
    items: list[POItemCreate] = []
    for chosen in order.lines:
        line: PurchaseRequestLine | None = lines_by_id.get(chosen.line_id)
        if line is None:
            raise _error(status.HTTP_400_BAD_REQUEST, f"Line {chosen.line_id} is not on this request")
        if line.converted_po_id is not None or chosen.line_id in used:
            raise _error(status.HTTP_409_CONFLICT, f"Line {chosen.line_id} has already been ordered")
        product_id = chosen.product_id or line.product_id
        if product_id is None:
            raise _error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"Line '{line.description}' has no product yet; choose one to order it",
            )
        price: Decimal = chosen.unit_price if chosen.unit_price is not None else line.estimated_unit_price
        used.add(chosen.line_id)
        items.append(POItemCreate(product_id=product_id, quantity=line.quantity, unit_price=price))
    return items


async def convert_request(db: AsyncSession, request_id: int, payload: ConvertRequest, actor: User) -> list[int]:
    """Turn an approved request into draft purchase orders, one per supplier; returns the new order ids.

    Each line can be ordered once. When every line has been ordered the request is marked converted; until then it
    stays approved so the rest can be ordered later.
    """
    request = await get_request(db, request_id, actor, for_update=True)
    if request.status != PurchaseRequestStatus.APPROVED:
        raise _error(
            status.HTTP_409_CONFLICT, f"Only an approved request can be ordered; this one is '{request.status.value}'"
        )

    used: set[int] = set()
    po_ids: list[int] = []
    lines_by_id = {line.id: line for line in request.lines}
    for order in payload.orders:
        items = _order_items(request, order, used)
        try:
            create = PurchaseOrderCreate(
                supplier_id=order.supplier_id,
                currency_code=request.currency_code,
                cost_centre_id=request.cost_centre_id,
                expected_delivery_date=order.expected_delivery_date,
                notes=order.notes or f"From purchase request {request.request_number}: {request.title}",
                items=items,
            )
        except ValidationError as exc:
            detail = "; ".join(str(error["msg"]).removeprefix("Value error, ") for error in exc.errors())
            raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, detail) from exc
        po = await po_draft_service.create_draft(db, create, actor, purchase_request_id=request.id)
        po_ids.append(po.id)
        for chosen in order.lines:
            lines_by_id[chosen.line_id].converted_po_id = po.id
            if chosen.product_id is not None and lines_by_id[chosen.line_id].product_id is None:
                lines_by_id[chosen.line_id].product_id = chosen.product_id

    if all(line.converted_po_id is not None for line in request.lines):
        request.status = PurchaseRequestStatus.CONVERTED
    await record_audit_event(
        db,
        user_id=actor.id,
        action="purchase_request_converted",
        entity_type="purchase_request",
        entity_id=request.id,
        extra_data={"purchase_order_ids": po_ids},
    )
    await db.commit()
    return po_ids
