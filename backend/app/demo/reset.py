"""Wiping the demo data and building it again."""

import logging

from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.base import Base
from app.demo.seed import DemoSeedSummary, seed_demo
from app.models.currency import Currency
from app.models.payment import PAYMENT_RUN_NUMBER_SEQUENCE
from app.models.purchase_order import PO_NUMBER_SEQUENCE
from app.models.purchase_request import REQUEST_NUMBER_SEQUENCE

logger = logging.getLogger(__name__)

# Reference data that a demo visitor cannot change and the migrations created: roles and what they may do, and the
# currency list. Everything else in the database is demo data.
KEPT_TABLES = frozenset({"roles", "permissions", "role_permissions", "currencies"})
DEMO_CURRENCIES = ("USD", "EUR", "GBP")
NUMBER_SEQUENCES = (PO_NUMBER_SEQUENCE, REQUEST_NUMBER_SEQUENCE, PAYMENT_RUN_NUMBER_SEQUENCE)


class DemoResetRefusedError(RuntimeError):
    """Raised when a reset is asked for outside the demo."""


def require_demo_mode(settings: Settings) -> None:
    """A reset empties the database, so it only ever runs when the deployment says it is a demo."""
    if not settings.demo_mode:
        raise DemoResetRefusedError("Refusing to reset: DEMO_MODE is not true. A reset deletes all data.")


async def wipe_demo_data(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Empty every table except the reference data, restart the number sequences and re-enable the demo currencies."""
    tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables if table.name not in KEPT_TABLES)
    async with session_factory() as db:
        await db.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))
        for sequence in NUMBER_SEQUENCES:
            await db.execute(text(f'ALTER SEQUENCE "{sequence.name}" RESTART'))
        await db.execute(update(Currency).where(Currency.code.in_(DEMO_CURRENCIES)).values(is_active=True))
        await db.commit()


async def reset_demo(settings: Settings, session_factory: async_sessionmaker[AsyncSession]) -> DemoSeedSummary:
    """Wipe and re-seed. Running it twice in a row gives the same company (same day, same data)."""
    require_demo_mode(settings)
    await wipe_demo_data(session_factory)
    return await seed_demo(settings, session_factory)
