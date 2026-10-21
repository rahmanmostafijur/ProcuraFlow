from datetime import UTC, date, datetime


def utc_today() -> date:
    # Not date.today(): that follows the host's time zone, so the same request could land on different days
    # on a developer laptop and in the (UTC) container, and disagree with timestamps Postgres reports in UTC.
    return datetime.now(UTC).date()
