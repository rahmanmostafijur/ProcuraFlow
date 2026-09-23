from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser, DbSession
from app.models.role import Role
from app.schemas.role import RoleRead

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("", response_model=list[RoleRead])
async def list_roles(db: DbSession, _: CurrentUser) -> list[Role]:
    result = await db.execute(select(Role).options(selectinload(Role.permissions)).order_by(Role.id))
    return list(result.scalars().all())
