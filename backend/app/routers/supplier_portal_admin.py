"""Internal side of the portal: inviting a supplier's contact and seeing which portal accounts a supplier has."""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession, require_permission
from app.core.permissions import SUPPLIER_ROLE
from app.core.security import hash_password
from app.models.role import Role
from app.models.user import User
from app.schemas.portal import PortalAccountRead, PortalInvite
from app.services import user_token_service
from app.services.audit_service import record_audit_event
from app.services.company_settings_service import get_company_settings
from app.services.supplier_document_service import ensure_supplier_exists

router = APIRouter(prefix="/suppliers/{supplier_id}", tags=["supplier-portal"])

RequireSupplierWrite = Annotated[User, Depends(require_permission("supplier:write"))]


@router.get("/portal-users", response_model=list[PortalAccountRead])
async def portal_users(supplier_id: int, db: DbSession, _: RequireSupplierWrite) -> list[User]:
    await ensure_supplier_exists(db, supplier_id)
    rows = await db.execute(select(User).where(User.supplier_id == supplier_id).order_by(User.id))
    return list(rows.scalars().all())


@router.post("/portal-invite", response_model=PortalAccountRead, status_code=status.HTTP_201_CREATED)
async def invite_portal_user(
    supplier_id: int, payload: PortalInvite, db: DbSession, actor: RequireSupplierWrite
) -> User:
    """Create a supplier account for one of the supplier's contacts and email them a link to choose a password."""
    supplier = await ensure_supplier_exists(db, supplier_id)
    if not supplier.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This supplier is not active")
    if (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists")
    role = (await db.execute(select(Role).where(Role.name == SUPPLIER_ROLE))).scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The supplier role has not been set up")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        # Nobody knows this password; the contact chooses their own through the emailed link.
        hashed_password=hash_password(secrets.token_urlsafe(32)),
        role_id=role.id,
        supplier_id=supplier.id,
    )
    db.add(user)
    await db.flush()
    company = await get_company_settings(db)
    await user_token_service.invite_user(db, user, company.company_name)
    await record_audit_event(
        db,
        user_id=actor.id,
        action="supplier_portal_invited",
        entity_type="supplier",
        entity_id=supplier.id,
        extra_data={"user_id": user.id},
    )
    await db.commit()
    await db.refresh(user)
    return user
