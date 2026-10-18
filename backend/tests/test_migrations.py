import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parents[1]
ENUM_TYPES_SQL = (
    "SELECT t.typname FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace "
    "WHERE n.nspname = 'public' AND t.typtype = 'e'"
)


def _alembic(database_url: str, *args: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": database_url},
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, f"alembic {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}"
    return result.stdout


async def _admin(sql: str) -> None:
    server_url = make_url(get_settings().test_database_url).set(database="postgres")
    engine = create_async_engine(server_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    async with engine.connect() as connection:
        await connection.execute(text(sql))
    await engine.dispose()


async def _schema(database_url: str) -> tuple[set[str], list[str]]:
    engine = create_async_engine(database_url, poolclass=NullPool)
    async with engine.connect() as connection:
        tables = set(await connection.run_sync(lambda sync: inspect(sync).get_table_names()))
        enums = [row[0] for row in await connection.execute(text(ENUM_TYPES_SQL))]
    await engine.dispose()
    return tables, enums


@pytest.fixture
async def scratch_database_url():
    name = f"pf_migrations_{uuid.uuid4().hex[:12]}"
    await _admin(f'CREATE DATABASE "{name}"')
    url = make_url(get_settings().test_database_url).set(database=name)
    try:
        yield url.render_as_string(hide_password=False)
    finally:
        await _admin(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def test_migration_history_has_a_single_head():
    output = _alembic(get_settings().test_database_url, "heads")

    assert output.count("(head)") == 1


async def test_migrations_round_trip_on_a_fresh_database(scratch_database_url: str):
    _alembic(scratch_database_url, "upgrade", "head")
    upgraded_tables, _ = await _schema(scratch_database_url)
    assert {"users", "purchase_orders", "refresh_tokens", "login_failures"} <= upgraded_tables

    _alembic(scratch_database_url, "downgrade", "base")
    downgraded_tables, leftover_enums = await _schema(scratch_database_url)
    assert downgraded_tables == {"alembic_version"}
    assert leftover_enums == []

    _alembic(scratch_database_url, "upgrade", "head")
    reupgraded_tables, _ = await _schema(scratch_database_url)
    assert reupgraded_tables == upgraded_tables
