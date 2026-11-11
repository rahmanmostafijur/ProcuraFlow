from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.demo_guard import require_demo_mode
from app.core.deps import DbSession
from app.demo.accounts import ACCOUNTS_BY_KEY, DEMO_ACCOUNTS
from app.models.role import Role
from app.models.user import User
from app.routers.auth import start_session
from app.schemas.auth import AccessTokenResponse

# Every route here answers 404 unless DEMO_MODE is on: outside the demo these endpoints do not exist.
router = APIRouter(prefix="/auth", tags=["demo"], dependencies=[Depends(require_demo_mode)])


class DemoAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # The value to send to /auth/demo-login.
    role: str
    role_name: str
    full_name: str
    email: str
    description: str
    # True for supplier-portal accounts, which land in the portal instead of the main app.
    is_portal: bool


class DemoLoginRequest(BaseModel):
    role: str


@router.get("/demo-accounts", response_model=list[DemoAccountRead])
async def list_demo_accounts() -> list[DemoAccountRead]:
    """Public: the roles the login page offers as one-click demo sign-ins."""
    return [
        DemoAccountRead(
            role=account.key,
            role_name=account.role_name,
            full_name=account.full_name,
            email=account.email,
            description=account.description,
            is_portal=account.is_portal,
        )
        for account in DEMO_ACCOUNTS
    ]


@router.post("/demo-login", response_model=AccessTokenResponse)
async def demo_login(payload: DemoLoginRequest, response: Response, db: DbSession) -> AccessTokenResponse:
    """Sign in as the demo user of a role, through the same session path as the password login."""
    account = ACCOUNTS_BY_KEY.get(payload.role)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown demo role")
    user = await db.scalar(
        select(User).options(selectinload(User.role).selectinload(Role.permissions)).where(User.email == account.email)
    )
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The demo data is not loaded yet; run python -m app.cli.demo_reset",
        )
    return await start_session(db, user, response)
