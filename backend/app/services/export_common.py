"""What every export dataset shares: its filters, how it reads rows in pages, and how it describes itself."""

from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Protocol

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.models.currency import Currency
from app.services.export_writer import Cell

PAGE_SIZE = 500


class HasId(Protocol):
    id: int


@dataclass(frozen=True)
class ExportFilters:
    date_from: date | None = None
    date_to: date | None = None
    status: str | None = None

    def as_audit(self) -> dict[str, str | None]:
        return {
            "date_from": self.date_from.isoformat() if self.date_from else None,
            "date_to": self.date_to.isoformat() if self.date_to else None,
            "status": self.status,
        }


RowSource = Callable[[AsyncSession, ExportFilters], AsyncIterator[Sequence[Cell]]]


@dataclass(frozen=True)
class Dataset:
    name: str
    filename: str
    header: Sequence[str]
    rows: RowSource
    # Values the ``status`` filter accepts; a status outside this set is a client error, not an empty file.
    statuses: frozenset[str]
    date_format: str = "%Y-%m-%d"


def validate_filters(dataset: Dataset, filters: ExportFilters) -> None:
    unprocessable = status.HTTP_422_UNPROCESSABLE_CONTENT
    if filters.date_from and filters.date_to and filters.date_from > filters.date_to:
        raise HTTPException(status_code=unprocessable, detail="date_from cannot be after date_to")
    if filters.status is not None and filters.status not in dataset.statuses:
        allowed = ", ".join(sorted(dataset.statuses))
        raise HTTPException(status_code=unprocessable, detail=f"status must be one of: {allowed}")


def day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


def day_after(day: date) -> datetime:
    return day_start(day + timedelta(days=1))


async def keyset_pages[T: HasId](
    db: AsyncSession, base: Select[tuple[T]], id_column: InstrumentedAttribute[int]
) -> AsyncIterator[Sequence[T]]:
    """``base`` read ``PAGE_SIZE`` rows at a time in id order, so memory stays flat however big the table is."""
    last_id = 0
    while True:
        page = (
            (await db.execute(base.where(id_column > last_id).order_by(id_column).limit(PAGE_SIZE)))
            .scalars()
            .unique()
            .all()
        )
        if not page:
            return
        yield page
        last_id = page[-1].id


async def minor_units_by_currency(db: AsyncSession) -> dict[str, int]:
    return {row.code: row.minor_units for row in (await db.execute(select(Currency.code, Currency.minor_units))).all()}
