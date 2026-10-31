from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.core.deps import DbSession, require_permission
from app.models.user import User
from app.services import gdpr_anonymise_service, gdpr_export_service

router = APIRouter(prefix="/gdpr", tags=["gdpr"])

RequireGdpr = Annotated[User, Depends(require_permission("gdpr:manage"))]


@router.get("/users/{user_id}/export")
async def export_user(user_id: int, db: DbSession, actor: RequireGdpr) -> dict[str, Any]:
    """Everything stored about a user account, as JSON."""
    return await gdpr_export_service.export_user(db, actor, user_id)


@router.post("/users/{user_id}/anonymise")
async def anonymise_user(user_id: int, db: DbSession, actor: RequireGdpr) -> dict[str, Any]:
    """Replace the user's name and email with placeholders and close the account. Financial records stay."""
    return await gdpr_anonymise_service.anonymise_user(db, actor, user_id)


@router.get("/suppliers/{supplier_id}/contact/export")
async def export_supplier_contact(supplier_id: int, db: DbSession, actor: RequireGdpr) -> dict[str, Any]:
    """The supplier's contact person and its portal accounts, as JSON."""
    return await gdpr_export_service.export_supplier_contact(db, actor, supplier_id)


@router.post("/suppliers/{supplier_id}/contact/anonymise")
async def anonymise_supplier_contact(supplier_id: int, db: DbSession, actor: RequireGdpr) -> dict[str, Any]:
    return await gdpr_anonymise_service.anonymise_supplier_contact(db, actor, supplier_id)
