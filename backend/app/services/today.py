"""Today's date as a dependency, so time-dependent answers (document expiry) can be pinned in tests."""

from datetime import date
from typing import Annotated

from fastapi import Depends

from app.core.clock import today_in
from app.core.deps import DbSession
from app.services.company_settings_service import get_company_settings


async def get_today(db: DbSession) -> date:
    """The calendar date in the company's time zone."""
    return today_in((await get_company_settings(db)).timezone)


Today = Annotated[date, Depends(get_today)]
