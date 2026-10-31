"""Format and checksum checks for bank details, so a mistyped account is refused when it is entered."""

import re

IBAN_PATTERN = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$")
BIC_PATTERN = re.compile(r"^[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?$")
ROUTING_PATTERN = re.compile(r"^\d{9}$")
ACCOUNT_NUMBER_PATTERN = re.compile(r"^[A-Z0-9]{1,34}$")
IBAN_MODULUS = 97
ABA_WEIGHTS = (3, 7, 1, 3, 7, 1, 3, 7, 1)


def compact(value: str) -> str:
    """Spaces and dashes are for readability only; they are not part of an account identifier."""
    return re.sub(r"[\s-]", "", value).upper()


def is_valid_iban(iban: str) -> bool:
    """ISO 13616: the rearranged number, read as an integer, leaves remainder 1 when divided by 97."""
    if not IBAN_PATTERN.fullmatch(iban):
        return False
    rearranged = iban[4:] + iban[:4]
    digits = "".join(str(int(char, 36)) for char in rearranged)
    return int(digits) % IBAN_MODULUS == 1


def is_valid_routing_number(routing: str) -> bool:
    """A US ABA routing number: nine digits whose weighted sum is a multiple of ten."""
    if not ROUTING_PATTERN.fullmatch(routing):
        return False
    return sum(int(digit) * weight for digit, weight in zip(routing, ABA_WEIGHTS, strict=True)) % 10 == 0
