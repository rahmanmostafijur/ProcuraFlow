from datetime import date

import pytest

from app.core.fiscal import fiscal_year_bounds, fiscal_year_of


@pytest.mark.parametrize(
    ("day", "start_month", "expected"),
    [
        (date(2026, 1, 1), 1, 2026),
        (date(2026, 12, 31), 1, 2026),
        (date(2026, 3, 31), 4, 2025),
        (date(2026, 4, 1), 4, 2026),
        (date(2026, 12, 31), 4, 2026),
        (date(2026, 9, 30), 10, 2025),
        (date(2026, 10, 1), 10, 2026),
    ],
)
def test_a_fiscal_year_is_named_after_the_calendar_year_it_starts_in(
    day: date, start_month: int, expected: int
) -> None:
    assert fiscal_year_of(day, start_month) == expected


def test_bounds_run_from_the_first_day_to_the_first_day_of_the_next_year() -> None:
    assert fiscal_year_bounds(2025, 4) == (date(2025, 4, 1), date(2026, 4, 1))
    assert fiscal_year_bounds(2026, 1) == (date(2026, 1, 1), date(2027, 1, 1))


def test_a_day_is_inside_the_bounds_of_its_own_fiscal_year_only() -> None:
    day = date(2026, 3, 31)
    year = fiscal_year_of(day, 4)

    start, end = fiscal_year_bounds(year, 4)

    assert start <= day < end
    next_start, next_end = fiscal_year_bounds(year + 1, 4)
    assert not next_start <= day < next_end
