import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import exists, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.uploads import ValidatedFile
from app.models.company_settings import COMPANY_SETTINGS_ID, CompanySettings
from app.models.currency import Currency
from app.models.purchase_order import PurchaseOrder
from app.models.user import User
from app.schemas.company_settings import BrandingRead, CompanySettingsRead, CompanySettingsUpdate
from app.services.audit_service import current_values, field_changes, record_audit_event
from app.storage import StorageBackend, new_storage_key

logger = logging.getLogger(__name__)

# What a new installation starts with; every value can be changed on the settings page.
DEFAULT_COMPANY_SETTINGS: dict[str, Any] = {
    "company_name": "ProcuraFlow",
    "brand_color": "#0F766E",
    "base_currency_code": "USD",
    "fiscal_year_start_month": 1,
    "date_format": "MM/DD/YYYY",
    "timezone": "UTC",
    "po_number_prefix": "PO",
    "invoice_tolerance_percent": Decimal("2.00"),
    "default_payment_terms_days": 30,
    "budget_block_over_budget": False,
    "budget_warn_percent": Decimal("80.00"),
}
LOGO_FOLDER = "logos"


async def get_company_settings(db: AsyncSession, *, for_update: bool = False) -> CompanySettings:
    """The settings row, created with the defaults the first time anything asks for it."""
    stmt = select(CompanySettings).where(CompanySettings.id == COMPANY_SETTINGS_ID)
    if for_update:
        stmt = stmt.with_for_update()
    row = await db.scalar(stmt)
    if row is None:
        # ON CONFLICT: two first requests racing each other both end up reading the same single row.
        await db.execute(
            insert(CompanySettings)
            .values(id=COMPANY_SETTINGS_ID, **DEFAULT_COMPANY_SETTINGS)
            .on_conflict_do_nothing(index_elements=[CompanySettings.id])
        )
        row = await db.scalar(stmt)
    assert row is not None  # noqa: S101 - inserted just above
    return row


def logo_url(row: CompanySettings) -> str | None:
    """Path under the API root; the version parameter makes browsers and mail clients fetch a replaced logo."""
    if row.logo_storage_key is None or row.logo_updated_at is None:
        return None
    return f"/company-settings/logo?v={int(row.logo_updated_at.timestamp())}"


def to_branding(row: CompanySettings) -> BrandingRead:
    return BrandingRead(company_name=row.company_name, brand_color=row.brand_color, logo_url=logo_url(row))


def to_read(row: CompanySettings) -> CompanySettingsRead:
    values = {name: getattr(row, name) for name in CompanySettingsRead.model_fields if name != "logo_url"}
    return CompanySettingsRead.model_validate({**values, "logo_url": logo_url(row)})


async def update_company_settings(db: AsyncSession, payload: CompanySettingsUpdate, user: User) -> CompanySettings:
    row = await get_company_settings(db, for_update=True)
    update_data = payload.model_dump(exclude_unset=True)
    new_base = update_data.get("base_currency_code")
    if new_base is not None and new_base != row.base_currency_code:
        await _ensure_base_currency_can_change(db, new_base)
    changes = field_changes(current_values(row, update_data), update_data)
    for field, value in update_data.items():
        setattr(row, field, value)
    row.updated_by = user.id
    if changes:
        await record_audit_event(
            db,
            user_id=user.id,
            action="company_settings_updated",
            entity_type="company_settings",
            entity_id=row.id,
            extra_data={"changes": changes},
        )
    await db.commit()
    await db.refresh(row)
    return row


async def _ensure_base_currency_can_change(db: AsyncSession, new_base: str) -> None:
    currency = await db.get(Currency, new_base)
    if currency is None or not currency.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Currency '{new_base}' is unknown or not active"
        )
    # Approved orders hold amounts converted into the current base currency; switching would orphan them.
    if await db.scalar(select(exists().where(PurchaseOrder.exchange_rate.is_not(None)))):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The base currency cannot change once purchase orders have been approved.",
        )


async def replace_logo(db: AsyncSession, storage: StorageBackend, image: ValidatedFile, user: User) -> CompanySettings:
    row = await get_company_settings(db, for_update=True)
    new_key = new_storage_key(LOGO_FOLDER, image.extension)
    await storage.save(new_key, image.data, image.content_type)

    old_key = row.logo_storage_key
    row.logo_storage_key = new_key
    row.logo_content_type = image.content_type
    row.logo_updated_at = datetime.now(UTC)
    row.updated_by = user.id
    await record_audit_event(
        db,
        user_id=user.id,
        action="company_logo_updated",
        entity_type="company_settings",
        entity_id=row.id,
        extra_data={"content_type": image.content_type, "bytes": len(image.data)},
    )
    await db.commit()
    await db.refresh(row)
    if old_key:
        await _delete_quietly(storage, old_key)
    return row


async def remove_logo(db: AsyncSession, storage: StorageBackend, user: User) -> CompanySettings:
    row = await get_company_settings(db, for_update=True)
    old_key = row.logo_storage_key
    if old_key is None:
        return row
    row.logo_storage_key = None
    row.logo_content_type = None
    row.logo_updated_at = datetime.now(UTC)
    row.updated_by = user.id
    await record_audit_event(
        db, user_id=user.id, action="company_logo_removed", entity_type="company_settings", entity_id=row.id
    )
    await db.commit()
    await db.refresh(row)
    await _delete_quietly(storage, old_key)
    return row


async def _delete_quietly(storage: StorageBackend, key: str) -> None:
    # The database no longer points at the file, so failing to delete it leaves an orphan, not a broken logo.
    try:
        await storage.delete(key)
    except OSError:
        logger.warning("could not delete replaced logo %s", key, exc_info=True)
