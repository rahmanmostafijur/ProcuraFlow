"""Jobs meant to run once a day from cron: `python -m app.cli.daily_jobs`."""

import asyncio
import logging

from app.db.session import AsyncSessionLocal, engine
from app.services.notification_service import notify_overdue_approvals

logger = logging.getLogger(__name__)


async def run() -> dict[str, int]:
    async with AsyncSessionLocal() as db:
        overdue = await notify_overdue_approvals(db)
    await engine.dispose()
    return {"overdue_approval_notifications": overdue}


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("Daily jobs finished: %s", asyncio.run(run()))


if __name__ == "__main__":
    main()
