from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo


def today_in(time_zone: str) -> date:
    """The calendar date right now in the company's time zone (an IANA name from the company settings)."""
    return datetime.now(ZoneInfo(time_zone)).date()


def utc_today() -> date:
    # Not date.today(): that follows the host's time zone, so the same request could land on different days
    # on a developer laptop and in the (UTC) container, and disagree with timestamps Postgres reports in UTC.
    return datetime.now(UTC).date()
