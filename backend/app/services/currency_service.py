from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.currency import Currency, ExchangeRate
from app.models.user import User
from app.schemas.currency import CurrencyCreate, CurrencyUpdate, ExchangeRateCreate
from app.services.audit_service import current_values, field_changes, record_audit_event
from app.services.company_settings_service import get_company_settings


async def get_active_currency(db: AsyncSession, code: str) -> Currency:
    """The currency if it exists and is switched on; 400 otherwise (it is a client mistake, not a missing page)."""
    currency = await db.get(Currency, code)
    if currency is None or not currency.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Currency '{code}' is unknown or not active"
        )
    return currency


async def get_currency_or_404(db: AsyncSession, code: str) -> Currency:
    currency = await db.get(Currency, code)
    if currency is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Currency not found")
    return currency


async def create_currency(db: AsyncSession, payload: CurrencyCreate, user: User) -> Currency:
    if await db.get(Currency, payload.code) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Currency '{payload.code}' already exists")
    currency = Currency(**payload.model_dump())
    db.add(currency)
    await record_audit_event(
        db, user_id=user.id, action="currency_created", entity_type="currency", extra_data={"code": payload.code}
    )
    await db.commit()
    return currency


async def update_currency(db: AsyncSession, code: str, payload: CurrencyUpdate, user: User) -> Currency:
    currency = await get_currency_or_404(db, code)
    update_data = payload.model_dump(exclude_unset=True)
    if update_data.get("is_active") is False and currency.code == (await get_company_settings(db)).base_currency_code:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The base currency cannot be switched off")
    changes = field_changes(current_values(currency, update_data), update_data)
    for field, value in update_data.items():
        setattr(currency, field, value)
    if changes:
        await record_audit_event(
            db,
            user_id=user.id,
            action="currency_updated",
            entity_type="currency",
            extra_data={"code": code, "changes": changes},
        )
    await db.commit()
    return currency


async def get_rate_in_force(db: AsyncSession, base_code: str, code: str, on_date: date) -> ExchangeRate | None:
    """The latest manually entered rate whose effective date is on or before ``on_date``."""
    stmt = (
        select(ExchangeRate)
        .where(
            ExchangeRate.base_currency_code == base_code,
            ExchangeRate.currency_code == code,
            ExchangeRate.effective_date <= on_date,
        )
        .order_by(ExchangeRate.effective_date.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def add_exchange_rate(db: AsyncSession, payload: ExchangeRateCreate, user: User) -> ExchangeRate:
    base_code = (await get_company_settings(db)).base_currency_code
    if payload.currency_code == base_code:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The base currency is always worth 1 of itself; enter rates for other currencies",
        )
    await get_active_currency(db, payload.currency_code)

    rate = ExchangeRate(
        base_currency_code=base_code,
        currency_code=payload.currency_code,
        rate=payload.rate,
        effective_date=payload.effective_date,
        created_by=user.id,
    )
    db.add(rate)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A rate for {payload.currency_code} on {payload.effective_date} already exists",
        ) from exc
    await record_audit_event(
        db,
        user_id=user.id,
        action="exchange_rate_added",
        entity_type="exchange_rate",
        entity_id=rate.id,
        extra_data={
            "base": base_code,
            "currency": payload.currency_code,
            "rate": str(payload.rate),
            "effective_date": payload.effective_date.isoformat(),
        },
    )
    await db.commit()
    await db.refresh(rate)
    return rate


async def delete_exchange_rate(db: AsyncSession, rate_id: int, user: User) -> None:
    rate = await db.get(ExchangeRate, rate_id)
    if rate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exchange rate not found")
    # Approved orders keep the rate they locked, so removing an entered rate cannot move any reported number.
    await record_audit_event(
        db,
        user_id=user.id,
        action="exchange_rate_deleted",
        entity_type="exchange_rate",
        entity_id=rate.id,
        extra_data={
            "currency": rate.currency_code,
            "rate": str(rate.rate),
            "effective_date": rate.effective_date.isoformat(),
        },
    )
    await db.delete(rate)
    await db.commit()


def lock_rate_value(rate: ExchangeRate | None, currency_code: str, base_code: str, on_date: date) -> Decimal:
    if currency_code == base_code:
        return Decimal(1)
    if rate is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"There is no {currency_code} to {base_code} exchange rate on or before {on_date}. "
                "Add one under Currencies before approving."
            ),
        )
    return rate.rate
