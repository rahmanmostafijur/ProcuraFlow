"""Restore the public demo: `python -m app.cli.demo_reset` (run it from a nightly cron).

Deletes all data except the roles and currencies, then builds the demo company again. It refuses to run unless
DEMO_MODE=true, because it empties the database.
"""

import asyncio
import logging

from app.core.config import Settings, get_settings
from app.db.session import AsyncSessionLocal, engine
from app.demo.accounts import DEMO_ACCOUNTS, demo_password
from app.demo.reset import DemoResetRefusedError, reset_demo

logger = logging.getLogger(__name__)


async def run(settings: Settings) -> None:
    try:
        summary = await reset_demo(settings, AsyncSessionLocal)
    finally:
        await engine.dispose()
    logger.info(
        "Demo restored: %s users, %s suppliers, %s purchase orders, %s invoices, %s payments",
        summary.users,
        summary.suppliers,
        summary.purchase_orders,
        summary.invoices,
        summary.payments,
    )
    logger.info("Demo accounts (password for all: %s)", demo_password(settings))
    for account in DEMO_ACCOUNTS:
        logger.info("  %s  %s", account.email, account.description)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(run(get_settings()))
    except DemoResetRefusedError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
