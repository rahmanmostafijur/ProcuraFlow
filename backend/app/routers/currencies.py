from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession, require_permission
from app.core.pagination import paginate
from app.models.currency import Currency, ExchangeRate
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.currency import (
    CurrencyCodeStr,
    CurrencyCreate,
    CurrencyRead,
    CurrencyUpdate,
    ExchangeRateCreate,
    ExchangeRateRead,
)
from app.services import currency_service
from app.services.company_settings_service import get_company_settings

router = APIRouter(tags=["currencies"])

RequireFinanceManage = Annotated[User, Depends(require_permission("finance:manage"))]


@router.get("/currencies", response_model=list[CurrencyRead])
async def list_currencies(db: DbSession, _: CurrentUser, active_only: bool = False) -> list[Currency]:
    stmt = select(Currency).order_by(Currency.code)
    if active_only:
        stmt = stmt.where(Currency.is_active.is_(True))
    return list((await db.execute(stmt)).scalars().all())


@router.post("/currencies", response_model=CurrencyRead, status_code=status.HTTP_201_CREATED)
async def create_currency(payload: CurrencyCreate, db: DbSession, current_user: RequireFinanceManage) -> Currency:
    return await currency_service.create_currency(db, payload, current_user)


@router.patch("/currencies/{code}", response_model=CurrencyRead)
async def update_currency(
    code: CurrencyCodeStr, payload: CurrencyUpdate, db: DbSession, current_user: RequireFinanceManage
) -> Currency:
    return await currency_service.update_currency(db, code, payload, current_user)


@router.get("/exchange-rates", response_model=PaginatedResponse[ExchangeRateRead])
async def list_exchange_rates(
    db: DbSession,
    _: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    currency_code: CurrencyCodeStr | None = None,
) -> PaginatedResponse[ExchangeRateRead]:
    """Rates entered against the current base currency, newest first."""
    base_code = (await get_company_settings(db)).base_currency_code
    stmt = (
        select(ExchangeRate)
        .where(ExchangeRate.base_currency_code == base_code)
        .order_by(ExchangeRate.effective_date.desc(), ExchangeRate.id.desc())
    )
    if currency_code is not None:
        stmt = stmt.where(ExchangeRate.currency_code == currency_code)
    return await paginate(db, stmt, page, page_size, ExchangeRateRead)


@router.post("/exchange-rates", response_model=ExchangeRateRead, status_code=status.HTTP_201_CREATED)
async def add_exchange_rate(
    payload: ExchangeRateCreate, db: DbSession, current_user: RequireFinanceManage
) -> ExchangeRate:
    return await currency_service.add_exchange_rate(db, payload, current_user)


@router.delete("/exchange-rates/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exchange_rate(rate_id: int, db: DbSession, current_user: RequireFinanceManage) -> Response:
    await currency_service.delete_exchange_rate(db, rate_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
