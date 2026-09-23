from typing import TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

T = TypeVar("T")


async def paginate(
    db: AsyncSession, stmt: Select, page: int, page_size: int
) -> tuple[list, int, int]:
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    result = await db.execute(stmt.limit(page_size).offset((page - 1) * page_size))
    items = list(result.scalars().unique().all())

    total_pages = (total + page_size - 1) // page_size if page_size else 0
    return items, total, total_pages
