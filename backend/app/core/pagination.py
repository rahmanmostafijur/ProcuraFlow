from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.schemas.common import PaginatedResponse


async def paginate[M, S: BaseModel](
    db: AsyncSession, stmt: Select[tuple[M]], page: int, page_size: int, schema: type[S]
) -> PaginatedResponse[S]:
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    result = await db.execute(stmt.limit(page_size).offset((page - 1) * page_size))
    items = [schema.model_validate(row, from_attributes=True) for row in result.scalars().unique().all()]

    total_pages = (total + page_size - 1) // page_size if page_size else 0
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)
