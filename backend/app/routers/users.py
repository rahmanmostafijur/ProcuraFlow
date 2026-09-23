from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import DbSession, require_permission
from app.core.pagination import paginate
from app.core.security import hash_password
from app.models.role import Role
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/users", tags=["users"])

RequireUserManage = Annotated[User, Depends(require_permission("user:manage"))]

_LOAD_OPTIONS = (selectinload(User.role).selectinload(Role.permissions),)


@router.get("", response_model=PaginatedResponse[UserRead])
async def list_users(
    db: DbSession,
    _: RequireUserManage,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
) -> PaginatedResponse[UserRead]:
    stmt = select(User).options(*_LOAD_OPTIONS).order_by(User.id)
    if search:
        stmt = stmt.where(User.full_name.ilike(f"%{search}%") | User.email.ilike(f"%{search}%"))

    items, total, total_pages = await paginate(db, stmt, page, page_size)
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, db: DbSession, current_user: RequireUserManage) -> User:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists")

    role = (await db.execute(select(Role).where(Role.id == payload.role_id))).scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role not found")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role_id=payload.role_id,
    )
    db.add(user)
    await db.flush()
    await record_audit_event(
        db, user_id=current_user.id, action="user_created", entity_type="user", entity_id=user.id
    )
    await db.commit()

    result = await db.execute(select(User).options(*_LOAD_OPTIONS).where(User.id == user.id))
    return result.scalar_one()


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int, payload: UserUpdate, db: DbSession, current_user: RequireUserManage
) -> User:
    result = await db.execute(select(User).options(*_LOAD_OPTIONS).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    update_data = payload.model_dump(exclude_unset=True)
    password = update_data.pop("password", None)
    if password:
        user.hashed_password = hash_password(password)
    for field, value in update_data.items():
        setattr(user, field, value)

    await record_audit_event(
        db, user_id=current_user.id, action="user_updated", entity_type="user", entity_id=user.id
    )
    await db.commit()

    result = await db.execute(select(User).options(*_LOAD_OPTIONS).where(User.id == user_id))
    return result.scalar_one()
