import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.core.database_url import asyncpg_connect_args
from app.db.base import Base
from app.db.locks import MIGRATION_LOCK_KEY
from app.models import *  # noqa: F401,F403  (registers all models on Base.metadata)

config = context.config
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.migrations_database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    # Instances that boot together all run this. The lock makes them take turns, and whoever is second
    # finds the schema already at head and does nothing. It has to be a session-level lock: a migration
    # that adds an enum value commits mid-run (autocommit block), which would release a transaction-scoped
    # one. Session locks are not reliable through a transaction-pooling PgBouncer, so point
    # MIGRATION_DATABASE_URL at the direct (non-pooler) host there.
    connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": MIGRATION_LOCK_KEY})
    connection.commit()  # end the implicit transaction; the session lock outlives it
    try:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    finally:
        connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK_KEY})
        connection.commit()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=asyncpg_connect_args(settings.migrations_database_url),
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
