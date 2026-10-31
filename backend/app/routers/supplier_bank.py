from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.deps import DbSession, require_permission
from app.models.user import User
from app.schemas.supplier_bank import BankDecision, BankDetailsInput, BankDetailsOverview, BankDetailsRead
from app.services import supplier_bank_service

router = APIRouter(prefix="/suppliers/{supplier_id}/bank-details", tags=["supplier-bank-details"])

RequireBankDetails = Annotated[User, Depends(require_permission(supplier_bank_service.PERMISSION))]


@router.get("", response_model=BankDetailsOverview)
async def bank_details(supplier_id: int, db: DbSession, _: RequireBankDetails) -> BankDetailsOverview:
    """The current details, the change waiting for approval (if any) and the history of earlier versions."""
    return await supplier_bank_service.get_overview(db, supplier_id)


@router.post("/changes", response_model=BankDetailsRead, status_code=status.HTTP_201_CREATED)
async def request_change(
    supplier_id: int, payload: BankDetailsInput, db: DbSession, actor: RequireBankDetails
) -> BankDetailsRead:
    """Propose new bank details. They take effect only when a different person approves them."""
    return await supplier_bank_service.request_change(db, actor, supplier_id, payload)


@router.post("/changes/{change_id}/approve", response_model=BankDetailsRead)
async def approve_change(
    supplier_id: int, change_id: int, payload: BankDecision, db: DbSession, actor: RequireBankDetails
) -> BankDetailsRead:
    return await supplier_bank_service.approve_change(db, actor, supplier_id, change_id, payload)


@router.post("/changes/{change_id}/reject", response_model=BankDetailsRead)
async def reject_change(
    supplier_id: int, change_id: int, payload: BankDecision, db: DbSession, actor: RequireBankDetails
) -> BankDetailsRead:
    return await supplier_bank_service.reject_change(db, actor, supplier_id, change_id, payload)
