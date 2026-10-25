from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.deps import CurrentUser, DbSession, require_permission
from app.models.tax_rate import TaxRate
from app.models.user import User
from app.schemas.tax_rate import TaxRateCreate, TaxRateRead, TaxRateUpdate
from app.services.audit_service import current_values, field_changes, record_audit_event

router = APIRouter(prefix="/tax-rates", tags=["tax-rates"])

RequireFinanceManage = Annotated[User, Depends(require_permission("finance:manage"))]


def _duplicate_name() -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A tax rate with this name already exists")


@router.get("", response_model=list[TaxRateRead])
async def list_tax_rates(db: DbSession, _: CurrentUser, active_only: bool = False) -> list[TaxRate]:
    stmt = select(TaxRate).order_by(TaxRate.name)
    if active_only:
        stmt = stmt.where(TaxRate.is_active.is_(True))
    return list((await db.execute(stmt)).scalars().all())


@router.post("", response_model=TaxRateRead, status_code=status.HTTP_201_CREATED)
async def create_tax_rate(payload: TaxRateCreate, db: DbSession, current_user: RequireFinanceManage) -> TaxRate:
    tax_rate = TaxRate(**payload.model_dump())
    db.add(tax_rate)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise _duplicate_name() from exc
    await record_audit_event(
        db, user_id=current_user.id, action="tax_rate_created", entity_type="tax_rate", entity_id=tax_rate.id
    )
    await db.commit()
    await db.refresh(tax_rate)
    return tax_rate


@router.patch("/{tax_rate_id}", response_model=TaxRateRead)
async def update_tax_rate(
    tax_rate_id: int, payload: TaxRateUpdate, db: DbSession, current_user: RequireFinanceManage
) -> TaxRate:
    tax_rate = await db.get(TaxRate, tax_rate_id)
    if tax_rate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tax rate not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field in ("name", "percentage", "tax_type", "is_inclusive", "is_reverse_charge", "is_active"):
        if field in update_data and update_data[field] is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"'{field}' cannot be empty")
    # The rule must hold for the rate as it will be after the edit, not just for the fields sent.
    final_reverse = update_data.get("is_reverse_charge", tax_rate.is_reverse_charge)
    final_percentage = update_data.get("percentage", tax_rate.percentage)
    if final_reverse and final_percentage != 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A reverse-charge rate must be 0%: the supplier charges no tax",
        )

    changes = field_changes(current_values(tax_rate, update_data), update_data)
    for field, value in update_data.items():
        setattr(tax_rate, field, value)
    if changes:
        await record_audit_event(
            db,
            user_id=current_user.id,
            action="tax_rate_updated",
            entity_type="tax_rate",
            entity_id=tax_rate.id,
            extra_data={"changes": changes},
        )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise _duplicate_name() from exc
    await db.refresh(tax_rate)
    return tax_rate
