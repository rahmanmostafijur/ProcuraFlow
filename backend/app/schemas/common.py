from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, PlainSerializer

from app.core.money import trim_money


def format_money(value: Decimal) -> str:
    """An exact decimal string with at least two decimals: 77.0000 -> "77.00", 12.345 stays "12.345".

    Amounts are stored with four decimals, but a currency rarely needs more than its minor units; trailing zeros
    beyond two are noise. The value is never passed through a float.
    """
    return format(trim_money(value), "f")


# An amount of money in API responses.
Money = Annotated[Decimal, PlainSerializer(format_money, return_type=str, when_used="json")]


class PaginatedResponse[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int
