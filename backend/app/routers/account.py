from fastapi import APIRouter, HTTPException, status

from app.core.deps import CurrentUser, DbSession
from app.core.security import hash_password, verify_password
from app.schemas.auth import ChangePasswordRequest, PasswordResetRequest, TokenPasswordRequest
from app.services.audit_service import record_audit_event
from app.services.refresh_token_service import revoke_all_sessions
from app.services.user_token_service import PURPOSE_INVITE, PURPOSE_RESET, consume_token, request_password_reset

router = APIRouter(prefix="/auth", tags=["account"])

INVALID_TOKEN = "This link is invalid or has expired"  # noqa: S105 - user-facing message, not a secret


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
async def request_reset(payload: PasswordResetRequest, db: DbSession) -> dict[str, str]:
    """Always answers the same way, so it cannot be used to find out which emails have accounts."""
    await request_password_reset(db, payload.email)
    await db.commit()
    return {"detail": "If an account exists for that email, a reset link is on its way."}


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_reset(payload: TokenPasswordRequest, db: DbSession) -> None:
    user = await consume_token(db, payload.token, PURPOSE_RESET, payload.password)
    if user is None:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_TOKEN)
    await record_audit_event(db, user_id=user.id, action="password_reset", entity_type="user", entity_id=user.id)
    await db.commit()


@router.post("/invitations/accept", status_code=status.HTTP_204_NO_CONTENT)
async def accept_invitation(payload: TokenPasswordRequest, db: DbSession) -> None:
    user = await consume_token(db, payload.token, PURPOSE_INVITE, payload.password)
    if user is None:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_TOKEN)
    await record_audit_event(db, user_id=user.id, action="invitation_accepted", entity_type="user", entity_id=user.id)
    await db.commit()


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(payload: ChangePasswordRequest, db: DbSession, current_user: CurrentUser) -> None:
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    current_user.hashed_password = hash_password(payload.new_password)
    await revoke_all_sessions(db, current_user.id)
    await record_audit_event(
        db, user_id=current_user.id, action="password_changed", entity_type="user", entity_id=current_user.id
    )
    await db.commit()
