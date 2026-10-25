"""Fiscal-year arithmetic.

A fiscal year is named after the calendar year in which it starts: with a start month of April, 2026-03-31 is in
fiscal year 2025 and 2026-04-01 is in fiscal year 2026. With a start month of January it is the calendar year.
"""

from datetime import date

MONTHS_PER_YEAR = 12


def fiscal_year_of(day: date, start_month: int) -> int:
    return day.year if day.month >= start_month else day.year - 1


def fiscal_year_bounds(fiscal_year: int, start_month: int) -> tuple[date, date]:
    """First day of the fiscal year and the first day of the next one (so the end is exclusive)."""
    start = date(fiscal_year, start_month, 1)
    return start, date(fiscal_year + 1, start_month, 1)
