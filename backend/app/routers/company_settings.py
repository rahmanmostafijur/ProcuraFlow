from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status

from app.core.deps import CurrentUser, DbSession, require_permission
from app.core.uploads import read_upload, validate_image
from app.models.user import User
from app.schemas.company_settings import BrandingRead, CompanySettingsRead, CompanySettingsUpdate
from app.services import company_settings_service as settings_service
from app.storage import StorageBackend, StoredObjectNotFoundError, get_storage

router = APIRouter(prefix="/company-settings", tags=["company-settings"])

RequireSettingsManage = Annotated[User, Depends(require_permission("settings:manage"))]
Storage = Annotated[StorageBackend, Depends(get_storage)]

MAX_LOGO_BYTES = 1024 * 1024
LOGO_CACHE_SECONDS = 24 * 60 * 60


@router.get("/branding", response_model=BrandingRead)
async def get_branding(db: DbSession) -> BrandingRead:
    """Public: the sign-in page shows the company's name, colour and logo before anyone is signed in."""
    return settings_service.to_branding(await settings_service.get_company_settings(db))


@router.get("/logo")
async def get_logo(db: DbSession, storage: Storage) -> Response:
    """Public, like the branding: it appears on the sign-in page and in emails."""
    row = await settings_service.get_company_settings(db)
    if row.logo_storage_key is None or row.logo_content_type is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No logo has been uploaded")
    try:
        data = await storage.read(row.logo_storage_key)
    except StoredObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No logo has been uploaded") from exc
    return Response(
        content=data,
        media_type=row.logo_content_type,
        headers={
            "Cache-Control": f"public, max-age={LOGO_CACHE_SECONDS}",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


@router.get("", response_model=CompanySettingsRead)
async def get_company_settings(db: DbSession, _: CurrentUser) -> CompanySettingsRead:
    return settings_service.to_read(await settings_service.get_company_settings(db))


@router.patch("", response_model=CompanySettingsRead)
async def update_company_settings(
    payload: CompanySettingsUpdate, db: DbSession, current_user: RequireSettingsManage
) -> CompanySettingsRead:
    row = await settings_service.update_company_settings(db, payload, current_user)
    return settings_service.to_read(row)


@router.put("/logo", response_model=CompanySettingsRead)
async def upload_logo(
    db: DbSession, storage: Storage, current_user: RequireSettingsManage, file: Annotated[UploadFile, File()]
) -> CompanySettingsRead:
    image = validate_image(await read_upload(file, MAX_LOGO_BYTES))
    row = await settings_service.replace_logo(db, storage, image, current_user)
    return settings_service.to_read(row)


@router.delete("/logo", response_model=CompanySettingsRead)
async def delete_logo(db: DbSession, storage: Storage, current_user: RequireSettingsManage) -> CompanySettingsRead:
    row = await settings_service.remove_logo(db, storage, current_user)
    return settings_service.to_read(row)
