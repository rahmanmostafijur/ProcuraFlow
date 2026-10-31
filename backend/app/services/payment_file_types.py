"""The inputs both bank file formats are built from, and the text rules they share."""

import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

SATURDAY = 5
CENTS = Decimal(100)


@dataclass(frozen=True)
class Payer:
    """The company's own account: the debtor in a SEPA file, the originator in an ACH file."""

    name: str
    iban: str | None
    bic: str | None
    routing_number: str | None
    account_number: str | None
    ach_company_id: str | None


@dataclass(frozen=True)
class PaymentLine:
    """One payment: one invoice of the run, paid to its supplier's current bank details."""

    reference: str
    payee_name: str
    amount: Decimal
    iban: str | None
    bic: str | None
    account_number: str | None
    routing_number: str | None


def next_business_day(day: date) -> date:
    """The next weekday after ``day``; bank holidays are not modelled."""
    following = day + timedelta(days=1)
    while following.weekday() >= SATURDAY:
        following += timedelta(days=1)
    return following


def to_cents(amount: Decimal) -> int:
    return int((amount * CENTS).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def ascii_text(value: str) -> str:
    """Accented letters folded to plain ones; anything that cannot be folded is dropped. Bank formats are ASCII."""
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
