from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.database_url import asyncpg_connect_args

# Serverless Postgres drops idle connections; recycling well inside that window avoids handing out dead ones.
POOL_RECYCLE_SECONDS = 300

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=POOL_RECYCLE_SECONDS,
    connect_args=asyncpg_connect_args(settings.database_url),
)
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
