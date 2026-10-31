"""A supplier's bank details, changed only with a second person's approval, with every earlier version kept.

A change is a ``pending`` version. It does nothing until someone other than the requester approves it; then the
current version becomes ``superseded`` (it stays in the history) and the pending one becomes current. Payment files
read only the current version. The audit log records which fields changed and the last four characters of the
account, never the full account number.
"""

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.enums import BankDetailsStatus
from app.models.notification import Notification
from app.models.supplier import Supplier
from app.models.supplier_bank import SupplierBankDetails
from app.models.user import User
from app.schemas.person import PersonRead
from app.schemas.supplier_bank import BankDecision, BankDetailsInput, BankDetailsOverview, BankDetailsRead
from app.services.audit_service import record_audit_event
from app.services.notification_service import users_with_permission
from app.services.supplier_document_service import ensure_supplier_exists

PERMISSION = "supplier:bank_details"
DETAIL_FIELDS = ("bank_account_name", "bank_country", "iban", "bic", "bank_account_number", "routing_number")
MASKED_TAIL = 4


def _now() -> datetime:
    return datetime.now(UTC)


def _person(user: User | None) -> PersonRead | None:
    return PersonRead(id=user.id, full_name=user.full_name) if user else None


def _to_read(version: SupplierBankDetails, requester: User, decider: User | None) -> BankDetailsRead:
    person = _person(requester)
    assert person is not None  # noqa: S101 - the requester column is not nullable
    return BankDetailsRead(
        id=version.id,
        supplier_id=version.supplier_id,
        status=version.status,
        bank_account_name=version.bank_account_name,
        bank_country=version.bank_country,
        iban=version.iban,
        bic=version.bic,
        bank_account_number=version.bank_account_number,
        routing_number=version.routing_number,
        requested_by=person,
        requested_at=version.requested_at,
        decided_by=_person(decider),
        decided_at=version.decided_at,
        decision_comment=version.decision_comment,
        superseded_at=version.superseded_at,
    )


def _masked(version: SupplierBankDetails) -> dict[str, str | None]:
    account = version.iban or version.bank_account_number or ""
    return {"account_tail": f"...{account[-MASKED_TAIL:]}" if account else None, "bank_country": version.bank_country}


async def get_current(db: AsyncSession, supplier_id: int) -> SupplierBankDetails | None:
    current: SupplierBankDetails | None = await db.scalar(
        select(SupplierBankDetails).where(
            SupplierBankDetails.supplier_id == supplier_id,
            SupplierBankDetails.status == BankDetailsStatus.CURRENT.value,
        )
    )
    return current


async def get_overview(db: AsyncSession, supplier_id: int) -> BankDetailsOverview:
    await ensure_supplier_exists(db, supplier_id)
    decider = aliased(User)
    rows = (
        await db.execute(
            select(SupplierBankDetails, User, decider)
            .join(User, User.id == SupplierBankDetails.requested_by)
            .outerjoin(decider, decider.id == SupplierBankDetails.decided_by)
            .where(SupplierBankDetails.supplier_id == supplier_id)
            .order_by(SupplierBankDetails.id.desc())
        )
    ).all()
    reads = [(version.status, _to_read(version, requester, approver)) for version, requester, approver in rows]
    return BankDetailsOverview(
        current=next((read for state, read in reads if state == BankDetailsStatus.CURRENT), None),
        pending=next((read for state, read in reads if state == BankDetailsStatus.PENDING), None),
        history=[read for state, read in reads if state in (BankDetailsStatus.SUPERSEDED, BankDetailsStatus.REJECTED)],
    )


async def _read_one(db: AsyncSession, version_id: int) -> BankDetailsRead:
    decider = aliased(User)
    row = (
        await db.execute(
            select(SupplierBankDetails, User, decider)
            .join(User, User.id == SupplierBankDetails.requested_by)
            .outerjoin(decider, decider.id == SupplierBankDetails.decided_by)
            .where(SupplierBankDetails.id == version_id)
            .execution_options(populate_existing=True)
        )
    ).one()
    return _to_read(*row)


def _conflict(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)


async def request_change(db: AsyncSession, actor: User, supplier_id: int, details: BankDetailsInput) -> BankDetailsRead:
    supplier = await ensure_supplier_exists(db, supplier_id)
    values = details.model_dump()
    current = await get_current(db, supplier_id)
    if current is not None and all(getattr(current, field) == values[field] for field in DETAIL_FIELDS):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="These are already the supplier's bank details"
        )
    pending = SupplierBankDetails(
        supplier_id=supplier_id, status=BankDetailsStatus.PENDING, requested_by=actor.id, **values
    )
    db.add(pending)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise _conflict("A bank details change is already waiting for approval") from exc
    changed = [field for field in DETAIL_FIELDS if current is None or getattr(current, field) != values[field]]
    await record_audit_event(
        db,
        user_id=actor.id,
        action="supplier_bank_change_requested",
        entity_type="supplier",
        entity_id=supplier_id,
        extra_data={"change_id": pending.id, "fields_changed": changed} | _masked(pending),
    )
    await _notify_approvers(db, supplier, actor)
    await db.commit()
    return await _read_one(db, pending.id)


async def _notify_approvers(db: AsyncSession, supplier: Supplier, requester: User) -> None:
    for user_id in await users_with_permission(db, PERMISSION):
        if user_id != requester.id:
            db.add(Notification(user_id=user_id, message=f"Bank details change awaiting approval: {supplier.name}"))


async def _locked_pending(db: AsyncSession, supplier_id: int, change_id: int) -> SupplierBankDetails:
    version = await db.scalar(
        select(SupplierBankDetails)
        .where(SupplierBankDetails.id == change_id, SupplierBankDetails.supplier_id == supplier_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank details change not found")
    if version.status != BankDetailsStatus.PENDING:
        raise _conflict(f"This change is already {version.status}")
    return version


async def approve_change(
    db: AsyncSession, actor: User, supplier_id: int, change_id: int, decision: BankDecision
) -> BankDetailsRead:
    pending = await _locked_pending(db, supplier_id, change_id)
    if pending.requested_by == actor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You requested this change, so a second person must approve it.",
        )
    now = _now()
    current = await get_current(db, supplier_id)
    if current is not None:
        current.status = BankDetailsStatus.SUPERSEDED
        current.superseded_at = now
        # The old version must stop being current before the new one becomes it (one current row per supplier).
        await db.flush()
    pending.status = BankDetailsStatus.CURRENT
    pending.decided_by = actor.id
    pending.decided_at = now
    pending.decision_comment = decision.comment
    await record_audit_event(
        db,
        user_id=actor.id,
        action="supplier_bank_change_approved",
        entity_type="supplier",
        entity_id=supplier_id,
        extra_data={
            "change_id": pending.id,
            "requested_by": pending.requested_by,
            "replaced_change_id": current.id if current else None,
        }
        | _masked(pending),
    )
    await db.commit()
    return await _read_one(db, pending.id)


async def reject_change(
    db: AsyncSession, actor: User, supplier_id: int, change_id: int, decision: BankDecision
) -> BankDetailsRead:
    """Anyone with the permission may reject, the requester included (withdrawing their own request)."""
    pending = await _locked_pending(db, supplier_id, change_id)
    pending.status = BankDetailsStatus.REJECTED
    pending.decided_by = actor.id
    pending.decided_at = _now()
    pending.decision_comment = decision.comment
    await record_audit_event(
        db,
        user_id=actor.id,
        action="supplier_bank_change_rejected",
        entity_type="supplier",
        entity_id=supplier_id,
        extra_data={"change_id": pending.id, "requested_by": pending.requested_by},
    )
    await db.commit()
    return await _read_one(db, pending.id)
