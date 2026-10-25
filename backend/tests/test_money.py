from decimal import Decimal

import pytest

from app.core.money import LineAmounts, compute_line, convert_to_base, quantize_money, sum_lines


@pytest.mark.parametrize(
    ("amount", "minor_units", "expected"),
    [
        ("2.345", 2, "2.35"),
        ("2.344", 2, "2.34"),
        ("-2.345", 2, "-2.35"),
        ("0.5", 0, "1"),
        ("1.0005", 3, "1.001"),
    ],
)
def test_rounding_is_half_up_to_the_minor_units(amount: str, minor_units: int, expected: str) -> None:
    assert quantize_money(Decimal(amount), minor_units) == Decimal(expected)


def test_exclusive_tax_is_added_on_top() -> None:
    line = compute_line(
        quantity=3, unit_price=Decimal("19.99"), tax_percent=Decimal("20"), tax_inclusive=False, minor_units=2
    )

    assert line == LineAmounts(net=Decimal("59.97"), tax=Decimal("11.99"), total=Decimal("71.96"))


def test_inclusive_tax_is_taken_out_of_the_gross() -> None:
    line = compute_line(
        quantity=1, unit_price=Decimal("119.00"), tax_percent=Decimal("19"), tax_inclusive=True, minor_units=2
    )

    assert line == LineAmounts(net=Decimal("100.00"), tax=Decimal("19.00"), total=Decimal("119.00"))


def test_inclusive_line_always_adds_up_after_rounding() -> None:
    line = compute_line(
        quantity=7, unit_price=Decimal("3.3333"), tax_percent=Decimal("21"), tax_inclusive=True, minor_units=2
    )

    assert line.net + line.tax == line.total == Decimal("23.33")


def test_sub_cent_unit_prices_round_once_per_line() -> None:
    line = compute_line(
        quantity=1000, unit_price=Decimal("0.0425"), tax_percent=Decimal("0"), tax_inclusive=False, minor_units=2
    )

    assert line.total == Decimal("42.50")


def test_zero_decimal_currency() -> None:
    line = compute_line(
        quantity=3, unit_price=Decimal("333.5"), tax_percent=Decimal("10"), tax_inclusive=False, minor_units=0
    )

    assert line == LineAmounts(net=Decimal("1001"), tax=Decimal("100"), total=Decimal("1101"))


def test_document_totals_sum_the_rounded_lines() -> None:
    # Each line's tax is 0.3340 -> 0.33; summing the rounded lines gives 0.99, rounding the raw 0.9999 would give 1.00.
    lines = [
        compute_line(
            quantity=1, unit_price=Decimal("1.6665"), tax_percent=Decimal("20"), tax_inclusive=False, minor_units=2
        )
        for _ in range(3)
    ]

    totals = sum_lines(lines)

    assert totals.subtotal == Decimal("5.01")
    assert totals.tax_total == Decimal("0.99")
    assert totals.grand_total == totals.subtotal + totals.tax_total


def test_empty_document_totals_are_zero() -> None:
    totals = sum_lines([])

    assert (totals.subtotal, totals.tax_total, totals.grand_total) == (Decimal(0), Decimal(0), Decimal(0))


def test_conversion_to_base_rounds_to_the_base_currency() -> None:
    assert convert_to_base(Decimal("100.00"), Decimal("1.08345678"), 2) == Decimal("108.35")
    assert convert_to_base(Decimal("1000"), Decimal("0.00645"), 2) == Decimal("6.45")
