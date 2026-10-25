"""Money rules: Decimal only, rounded per line, half-up, to the currency's minor units.

Every stored amount is computed here, so the PO screen, the PDF, reports and invoice matching can never
disagree by a rounding step. Unit prices may carry up to four decimals; line and document amounts are
always rounded to the currency (two decimals for USD, none for JPY, three for BHD).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal("0")
HUNDRED = Decimal("100")
UNIT_PRICE_DECIMALS = 4
RATE_DECIMALS = 8


MIN_DISPLAY_DECIMALS = 2


def trim_money(value: Decimal) -> Decimal:
    """Drop trailing zeros but keep at least two decimals: 77.0000 -> 77.00, 12.345 stays 12.345, 10 -> 10.00."""
    normalized = value.normalize()
    exponent = normalized.as_tuple().exponent
    if isinstance(exponent, int) and exponent > -MIN_DISPLAY_DECIMALS:
        return normalized.quantize(Decimal(1).scaleb(-MIN_DISPLAY_DECIMALS))
    return normalized


def quantize_money(amount: Decimal, minor_units: int) -> Decimal:
    return amount.quantize(Decimal(1).scaleb(-minor_units), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class LineAmounts:
    net: Decimal
    tax: Decimal
    total: Decimal


@dataclass(frozen=True)
class DocumentTotals:
    subtotal: Decimal
    tax_total: Decimal
    grand_total: Decimal


def compute_line(
    *, quantity: int, unit_price: Decimal, tax_percent: Decimal, tax_inclusive: bool, minor_units: int
) -> LineAmounts:
    """Amounts for one line.

    Exclusive tax is added on top of quantity x price. Inclusive tax is already inside that figure, so it is
    taken out of the gross: tax = gross x rate / (100 + rate). Either way net + tax == total exactly.
    """
    gross_or_net = quantize_money(Decimal(quantity) * unit_price, minor_units)
    if tax_inclusive:
        tax = quantize_money(gross_or_net * tax_percent / (HUNDRED + tax_percent), minor_units)
        return LineAmounts(net=gross_or_net - tax, tax=tax, total=gross_or_net)
    tax = quantize_money(gross_or_net * tax_percent / HUNDRED, minor_units)
    return LineAmounts(net=gross_or_net, tax=tax, total=gross_or_net + tax)


def sum_lines(lines: Iterable[LineAmounts]) -> DocumentTotals:
    """Document totals are sums of already-rounded lines, never a re-rounding of the unrounded total."""
    subtotal = tax_total = ZERO
    for line in lines:
        subtotal += line.net
        tax_total += line.tax
    return DocumentTotals(subtotal=subtotal, tax_total=tax_total, grand_total=subtotal + tax_total)


def convert_to_base(amount: Decimal, rate: Decimal, base_minor_units: int) -> Decimal:
    """``rate`` is base-currency units per one unit of the document currency."""
    return quantize_money(amount * rate, base_minor_units)
