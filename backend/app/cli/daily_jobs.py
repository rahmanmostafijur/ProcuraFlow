"""Jobs meant to run once a day from cron: `python -m app.cli.daily_jobs`."""

import asyncio
import logging

from app.core.clock import today_in
from app.db.session import AsyncSessionLocal, engine
from app.services.company_settings_service import get_company_settings
from app.services.notification_service import notify_expiring_supplier_documents, notify_overdue_approvals

logger = logging.getLogger(__name__)


async def run() -> dict[str, int]:
    async with AsyncSessionLocal() as db:
        overdue = await notify_overdue_approvals(db)
        today = today_in((await get_company_settings(db)).timezone)
        documents = await notify_expiring_supplier_documents(db, today)
    await engine.dispose()
    return {"overdue_approval_notifications": overdue, "supplier_document_notifications": documents}


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("Daily jobs finished: %s", asyncio.run(run()))


if __name__ == "__main__":
    main()
