from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession, require_permission
from app.models.category import Category
from app.models.user import User
from app.schemas.category import CategoryCreate, CategoryRead
from app.services.audit_service import record_audit_event

router = APIRouter(prefix="/categories", tags=["categories"])

RequireProductWrite = Annotated[User, Depends(require_permission("product:write"))]


@router.get("", response_model=list[CategoryRead])
async def list_categories(db: DbSession, _: CurrentUser) -> list[Category]:
    result = await db.execute(select(Category).order_by(Category.name))
    return list(result.scalars().all())


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryCreate, db: DbSession, current_user: RequireProductWrite
) -> Category:
    category = Category(name=payload.name)
    db.add(category)
    await db.flush()
    await record_audit_event(
        db, user_id=current_user.id, action="category_created", entity_type="category", entity_id=category.id
    )
    await db.commit()
    await db.refresh(category)
    return category
