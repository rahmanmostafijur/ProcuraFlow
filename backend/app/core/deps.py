from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.permissions import SUPPLIER_ROLE
from app.core.security import TokenError, decode_token
from app.db.session import get_db
from app.models.role import Role
from app.models.user import User

PORTAL_PERMISSION = "portal:access"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_authenticated_user(token: Annotated[str, Depends(oauth2_scheme)], db: DbSession) -> User:
    """Whoever the token belongs to, supplier-portal accounts included. Only the auth routes use this directly."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token, expected_type="access")
    except TokenError as exc:
        raise credentials_exception from exc

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    result = await db.execute(
        select(User).options(selectinload(User.role).selectinload(Role.permissions)).where(User.id == int(user_id))
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def is_supplier_account(user: User) -> bool:
    return user.supplier_id is not None or user.role.name == SUPPLIER_ROLE


async def get_current_user(user: Annotated[User, Depends(get_authenticated_user)]) -> User:
    """An internal user. Supplier accounts are refused here, so no internal endpoint can ever answer one of them:
    the portal has its own dependency (``get_portal_user``) and its own routes."""
    if is_supplier_account(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Supplier accounts can only use the portal")
    return user


async def get_portal_user(user: Annotated[User, Depends(get_authenticated_user)]) -> User:
    """A supplier account linked to a supplier. Everything under /portal is scoped by that supplier, never by the
    request."""
    if user.supplier_id is None or not has_permission(user, PORTAL_PERMISSION):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This area is for supplier accounts")
    return user


AnyUser = Annotated[User, Depends(get_authenticated_user)]
CurrentUser = Annotated[User, Depends(get_current_user)]
PortalUser = Annotated[User, Depends(get_portal_user)]


def has_permission(user: User, permission_code: str) -> bool:
    """Whether the user's role grants the permission. The user must have been loaded with role and permissions."""
    return any(permission.code == permission_code for permission in user.role.permissions)


def require_permission(permission_code: str) -> Callable[[CurrentUser], Awaitable[User]]:
    async def _checker(current_user: CurrentUser) -> User:
        permission_codes = {p.code for p in current_user.role.permissions}
        if permission_code not in permission_codes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You do not have the '{permission_code}' permission",
            )
        return current_user

    return _checker
