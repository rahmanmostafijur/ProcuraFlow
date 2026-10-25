from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from app.core.clock import today_in
from app.core.deps import has_permission
from app.core.money import quantize_money
from app.models.approval import ApprovalStep
from app.models.currency import Currency
from app.models.enums import ApprovalDocumentType, PurchaseRequestStatus
from app.models.product import Product
from app.models.purchase_request import REQUEST_NUMBER_SEQUENCE, PurchaseRequest, PurchaseRequestLine
from app.models.supplier import Supplier
from app.models.user import User
from app.schemas.purchase_request import PurchaseRequestCreate, PurchaseRequestUpdate, RequestLineWrite
from app.services import approval_adapters, approval_engine, catalog_service
from app.services.approval_queue_service import queue_for
from app.services.audit_service import record_audit_event
from app.services.budget_service import get_active_cost_centre
from app.services.company_settings_service import get_company_settings
from app.services.currency_service import get_active_currency
from app.services.po_pricing import to_base_amount

READ_ALL_PERMISSION = "request:read_all"
EDITABLE = (PurchaseRequestStatus.DRAFT, PurchaseRequestStatus.REJECTED)
CANCELLABLE = (PurchaseRequestStatus.DRAFT, PurchaseRequestStatus.REJECTED, PurchaseRequestStatus.SUBMITTED)

REQUEST_LOAD = (selectinload(PurchaseRequest.requester), selectinload(PurchaseRequest.lines))


def _error(code: int, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail=message)


async def _can_view(db: AsyncSession, request: PurchaseRequest, viewer: User) -> bool:
    """The requester, people who see every request, and approvers: someone who decided a step, holds the approve
    permission or a role named by one of its steps, or can decide it now as a delegate."""
    if request.requester_id == viewer.id or has_permission(viewer, READ_ALL_PERMISSION):
        return True
    if has_permission(viewer, "request:approve"):
        return True
    involved = await db.scalar(
        select(func.count())
        .select_from(ApprovalStep)
        .where(
            ApprovalStep.document_type == ApprovalDocumentType.PURCHASE_REQUEST,
            ApprovalStep.document_id == request.id,
            (ApprovalStep.decided_by == viewer.id)
            | (ApprovalStep.on_behalf_of == viewer.id)
            | (ApprovalStep.approver_role_id == viewer.role_id),
        )
    )
    if involved:
        return True
    return any(
        item.document_type == ApprovalDocumentType.PURCHASE_REQUEST and item.document_id == request.id
        for item in await queue_for(db, viewer)
    )


async def get_request(db: AsyncSession, request_id: int, viewer: User, *, for_update: bool = False) -> PurchaseRequest:
    """The request if the viewer may see it; a request they may not see is reported as not found, never as forbidden."""
    stmt = select(PurchaseRequest).options(*REQUEST_LOAD).where(PurchaseRequest.id == request_id)
    if for_update:
        stmt = stmt.with_for_update(of=PurchaseRequest)
    request = await db.scalar(stmt.execution_options(populate_existing=True))
    if request is None or not await _can_view(db, request, viewer):
        raise _error(status.HTTP_404_NOT_FOUND, "Purchase request not found")
    return request


def scoped_list_statement(
    viewer: User, status_filter: PurchaseRequestStatus | None, mine: bool
) -> Select[tuple[PurchaseRequest]]:
    """Employees see their own requests; people who see every request can narrow to their own with ``mine``."""
    stmt = select(PurchaseRequest).options(*REQUEST_LOAD).order_by(PurchaseRequest.created_at.desc())
    if mine or not has_permission(viewer, READ_ALL_PERMISSION):
        stmt = stmt.where(PurchaseRequest.requester_id == viewer.id)
    if status_filter is not None:
        stmt = stmt.where(PurchaseRequest.status == status_filter)
    return stmt


async def _price_lines(
    db: AsyncSession, lines: list[RequestLineWrite], currency: Currency
) -> tuple[list[PurchaseRequestLine], Decimal]:
    settings = await get_company_settings(db)
    today = today_in(settings.timezone)
    product_ids = {line.product_id for line in lines if line.product_id is not None}
    supplier_ids = {line.supplier_id for line in lines if line.supplier_id is not None}
    if product_ids:
        found = set((await db.execute(select(Product.id).where(Product.id.in_(product_ids)))).scalars())
        if product_ids - found:
            raise _error(status.HTTP_400_BAD_REQUEST, f"Unknown product ids: {sorted(product_ids - found)}")
    if supplier_ids:
        found = set((await db.execute(select(Supplier.id).where(Supplier.id.in_(supplier_ids)))).scalars())
        if supplier_ids - found:
            raise _error(status.HTTP_400_BAD_REQUEST, f"Unknown supplier ids: {sorted(supplier_ids - found)}")

    priced: list[PurchaseRequestLine] = []
    total = Decimal(0)
    for line in lines:
        product_id, supplier_id, price = line.product_id, line.supplier_id, line.estimated_unit_price
        if line.catalog_item_id is not None:
            item = await catalog_service.get_usable_item(db, line.catalog_item_id, today)
            if item.currency_code != currency.code:
                raise _error(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    f"Catalog item {item.id} is priced in {item.currency_code}, but this request is in {currency.code}",
                )
            product_id, supplier_id = item.product_id, item.supplier_id
            price = item.contract_price if price is None else price
        if price is None:
            raise _error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"Line '{line.description}' needs an estimated price (or a catalog item)",
            )
        line_total = quantize_money(Decimal(line.quantity) * price, currency.minor_units)
        total += line_total
        priced.append(
            PurchaseRequestLine(
                description=line.description,
                catalog_item_id=line.catalog_item_id,
                product_id=product_id,
                supplier_id=supplier_id,
                quantity=line.quantity,
                unit=line.unit,
                estimated_unit_price=price,
                line_total=line_total,
            )
        )
    return priced, total


async def _next_request_number(db: AsyncSession) -> str:
    number = await db.scalar(select(REQUEST_NUMBER_SEQUENCE.next_value()))
    return f"PR-{datetime.now(UTC).year}-{number:05d}"


async def create_request(db: AsyncSession, payload: PurchaseRequestCreate, requester: User) -> PurchaseRequest:
    settings = await get_company_settings(db)
    currency = await get_active_currency(db, payload.currency_code or settings.base_currency_code)
    if payload.cost_centre_id is not None:
        await get_active_cost_centre(db, payload.cost_centre_id)
    lines, total = await _price_lines(db, payload.lines, currency)

    request = PurchaseRequest(
        request_number=await _next_request_number(db),
        requester_id=requester.id,
        title=payload.title,
        notes=payload.notes,
        cost_centre_id=payload.cost_centre_id,
        currency_code=currency.code,
        needed_by=payload.needed_by,
        status=PurchaseRequestStatus.DRAFT,
        estimated_total=total,
    )
    request.lines = lines
    db.add(request)
    await db.flush()
    await record_audit_event(
        db,
        user_id=requester.id,
        action="purchase_request_created",
        entity_type="purchase_request",
        entity_id=request.id,
        extra_data={"number": request.request_number},
    )
    await db.commit()
    return await get_request(db, request.id, requester)


async def update_request(
    db: AsyncSession, request_id: int, payload: PurchaseRequestUpdate, actor: User
) -> PurchaseRequest:
    request = await get_request(db, request_id, actor, for_update=True)
    if request.requester_id != actor.id:
        raise _error(status.HTTP_403_FORBIDDEN, "Only the person who raised a request can edit it")
    if request.status not in EDITABLE:
        raise _error(status.HTTP_409_CONFLICT, f"A request that is '{request.status.value}' can no longer be edited")

    update_data = payload.model_dump(exclude_unset=True, exclude={"lines"})
    for field in ("title", "currency_code"):
        if field in update_data and update_data[field] is None:
            raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, f"'{field}' cannot be empty")
    if update_data.get("cost_centre_id") is not None:
        await get_active_cost_centre(db, update_data["cost_centre_id"])
    new_currency = update_data.get("currency_code", request.currency_code)
    currency = await get_active_currency(db, new_currency)
    currency_changed = new_currency != request.currency_code

    for field, value in update_data.items():
        setattr(request, field, value)
    if payload.lines is not None or currency_changed:
        # A new currency re-rounds the lines that are kept; new lines replace them.
        write_lines = (
            payload.lines
            if payload.lines is not None
            else [
                RequestLineWrite(
                    description=line.description,
                    quantity=line.quantity,
                    unit=line.unit,
                    estimated_unit_price=line.estimated_unit_price,
                    catalog_item_id=line.catalog_item_id,
                    product_id=line.product_id,
                    supplier_id=line.supplier_id,
                )
                for line in request.lines
            ]
        )
        lines, total = await _price_lines(db, write_lines, currency)
        request.lines.clear()
        await db.flush()
        request.lines = lines
        request.estimated_total = total
    await record_audit_event(
        db,
        user_id=actor.id,
        action="purchase_request_updated",
        entity_type="purchase_request",
        entity_id=request.id,
        extra_data={"fields": sorted([*update_data, *(["lines"] if payload.lines is not None else [])])},
    )
    await db.commit()
    return await get_request(db, request_id, actor)


async def submit_request(db: AsyncSession, request_id: int, actor: User) -> PurchaseRequest:
    request = await get_request(db, request_id, actor, for_update=True)
    if request.requester_id != actor.id:
        raise _error(status.HTTP_403_FORBIDDEN, "Only the person who raised a request can submit it")
    if request.status not in EDITABLE:
        raise _error(status.HTTP_409_CONFLICT, f"A request that is '{request.status.value}' cannot be submitted")
    if not request.lines:
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Add at least one line before submitting")

    amount_base = await to_base_amount(db, request.estimated_total, request.currency_code)
    request.base_estimated_total = amount_base
    request.status = PurchaseRequestStatus.SUBMITTED
    request.submitted_at = datetime.now(UTC)
    request.decided_at = None
    request.rejection_reason = None
    await approval_engine.open_round(db, approval_adapters.request_subject(request, amount_base))
    await record_audit_event(
        db,
        user_id=actor.id,
        action="purchase_request_submitted",
        entity_type="purchase_request",
        entity_id=request.id,
        extra_data={"amount_base": str(amount_base)},
    )
    await db.commit()
    return await get_request(db, request_id, actor)


async def cancel_request(db: AsyncSession, request_id: int, actor: User) -> PurchaseRequest:
    request = await get_request(db, request_id, actor, for_update=True)
    if request.requester_id != actor.id:
        raise _error(status.HTTP_403_FORBIDDEN, "Only the person who raised a request can cancel it")
    if request.status not in CANCELLABLE:
        raise _error(status.HTTP_409_CONFLICT, f"A request that is '{request.status.value}' cannot be cancelled")
    await approval_engine.skip_open_steps(db, ApprovalDocumentType.PURCHASE_REQUEST, request.id)
    request.status = PurchaseRequestStatus.CANCELLED
    await record_audit_event(
        db, user_id=actor.id, action="purchase_request_cancelled", entity_type="purchase_request", entity_id=request.id
    )
    await db.commit()
    return await get_request(db, request_id, actor)


async def decide_request(
    db: AsyncSession, request_id: int, actor: User, *, approve: bool, comment: str | None
) -> PurchaseRequest:
    """Approve or reject the request's current step. Anyone who is not eligible gets a 403 from the engine."""
    # The same view scope as reading: someone who could not open the request cannot decide it either, and is told
    # it does not exist. The engine then decides whether this approver is allowed to act on it.
    request = await get_request(db, request_id, actor, for_update=True)
    subject = approval_adapters.request_subject(request)
    await approval_engine.decide(db, subject, actor, approve=approve, comment=comment)
    await db.commit()
    return await get_request(db, request_id, actor)
