"""The one CSV writer behind every export: formula-injection protection, number formatting and chunked output.

Datasets hand it typed cells. Free text (``str``) is neutralised with ``neutralize_formula``; numbers are never run
through it, so a negative amount stays a number and is not mangled into text. Rows are encoded in chunks as they are
produced, so a large export is never held in memory as one string.
"""

import csv
import io
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.core.csv_safety import neutralize_formula

CHUNK_ROWS = 500


@dataclass(frozen=True)
class Fixed:
    """A decimal printed with exactly ``places`` decimals, or up to ``max_places`` when extra precision is real."""

    value: Decimal
    places: int = 2
    max_places: int | None = None

    def text(self) -> str:
        top = max(self.places, self.max_places or self.places)
        rendered = str(self.value.quantize(Decimal(1).scaleb(-top), rounding=ROUND_HALF_UP))
        if top > self.places:
            whole, _, fraction = rendered.partition(".")
            fraction = fraction.rstrip("0").ljust(self.places, "0")
            rendered = f"{whole}.{fraction}" if fraction else whole
        return rendered


Cell = str | int | bool | date | Fixed | None


def encode_cell(cell: Cell, date_format: str = "%Y-%m-%d") -> str:
    if cell is None:
        return ""
    if isinstance(cell, bool):
        return "true" if cell else "false"
    if isinstance(cell, Fixed):
        return cell.text()
    if isinstance(cell, date):
        return cell.strftime(date_format)
    if isinstance(cell, int):
        return str(cell)
    return neutralize_formula(cell)


async def csv_chunks(
    header: Sequence[str], rows: AsyncIterator[Sequence[Cell]], date_format: str = "%Y-%m-%d"
) -> AsyncIterator[str]:
    """The CSV text in pieces: the header first, then ``CHUNK_ROWS`` rows at a time."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    pending = 0
    async for row in rows:
        writer.writerow([encode_cell(cell, date_format) for cell in row])
        pending += 1
        if pending >= CHUNK_ROWS:
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate()
            pending = 0
    if buffer.tell():
        yield buffer.getvalue()
