import math
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.auth_cookie import REFRESH_COOKIE_NAME, refresh_cookie_options
from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.core.rate_limit import LoginAttemptGuard, get_login_guard
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import AccessTokenResponse, LoginRequest
from app.schemas.user import UserRead
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/auth", tags=["auth"])

LoginGuard = Annotated[LoginAttemptGuard, Depends(get_login_guard)]
UNKNOWN_CLIENT = "unknown"
SECONDS_PER_MINUTE = 60


def _too_many_attempts(retry_after_seconds: int) -> HTTPException:
    minutes = math.ceil(retry_after_seconds / SECONDS_PER_MINUTE)
    unit = "minute" if minutes == 1 else "minutes"
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Too many failed sign-in attempts. Try again in {minutes} {unit}.",
        headers={"Retry-After": str(retry_after_seconds)},
    )


@router.post("/login", response_model=AccessTokenResponse)
async def login(
    payload: LoginRequest, request: Request, response: Response, db: DbSession, guard: LoginGuard
) -> AccessTokenResponse:
    client_ip = request.client.host if request.client else UNKNOWN_CLIENT
    retry_after = guard.retry_after(payload.email, client_ip)
    if retry_after:
        raise _too_many_attempts(retry_after)

    result = await db.execute(
        select(User)
        .options(selectinload(User.role).selectinload(Role.permissions))
        .where(User.email == payload.email)
    )
    user = result.scalar_one_or_none()

    if user is None or not user.is_active or not verify_password(payload.password, user.hashed_password):
        guard.record_failure(payload.email, client_ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    guard.record_success(payload.email)
    await record_audit_event(db, user_id=user.id, action="login", entity_type="user", entity_id=user.id)
    await db.commit()

    response.set_cookie(
        REFRESH_COOKIE_NAME,
        create_refresh_token(str(user.id)),
        **refresh_cookie_options(get_settings()),
    )
    return AccessTokenResponse(access_token=create_access_token(str(user.id), user.role.name))


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh_access_token(
    db: DbSession,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
) -> AccessTokenResponse:
    if refresh_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in")
    try:
        token_payload = decode_token(refresh_token, expected_type="refresh")
    except TokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    user_id = int(token_payload["sub"])
    result = await db.execute(select(User).options(selectinload(User.role)).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is no longer active")

    return AccessTokenResponse(access_token=create_access_token(str(user.id), user.role.name))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout() -> Response:
    """Drop the refresh cookie. Access tokens are short-lived and held in memory by the client."""
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    options = refresh_cookie_options(get_settings())
    response.delete_cookie(
        REFRESH_COOKIE_NAME,
        path=options["path"],
        secure=options["secure"],
        httponly=options["httponly"],
        samesite=options["samesite"],
    )
    return response


@router.get("/me", response_model=UserRead)
async def read_current_user(current_user: CurrentUser) -> User:
    return current_user
