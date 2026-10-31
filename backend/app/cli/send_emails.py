"""Deliver queued email: `python -m app.cli.send_emails` (run it from cron or after a mail outage)."""

import asyncio
import logging

from app.db.session import AsyncSessionLocal, engine
from app.services.email_service import deliver_queued

logger = logging.getLogger(__name__)


async def run() -> int:
    async with AsyncSessionLocal() as db:
        attempted = await deliver_queued(db)
    await engine.dispose()
    return attempted


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    attempted = asyncio.run(run())
    logger.info("Attempted %s queued message(s)", attempted)


if __name__ == "__main__":
    main()
