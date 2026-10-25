from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status

from app.core.deps import CurrentUser, DbSession
from app.core.uploads import read_upload
from app.models.enums import AttachmentParentType
from app.schemas.attachment import AttachmentRead
from app.services import attachment_service
from app.storage import StorageBackend, get_storage

router = APIRouter(prefix="/attachments", tags=["attachments"])

Storage = Annotated[StorageBackend, Depends(get_storage)]


@router.get("", response_model=list[AttachmentRead])
async def list_attachments(
    db: DbSession, user: CurrentUser, parent_type: AttachmentParentType, parent_id: Annotated[int, Query(ge=1)]
) -> list[AttachmentRead]:
    return await attachment_service.list_attachments(db, user, parent_type, parent_id)


@router.post("", response_model=AttachmentRead, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    db: DbSession,
    storage: Storage,
    user: CurrentUser,
    parent_type: AttachmentParentType,
    parent_id: Annotated[int, Query(ge=1)],
    file: Annotated[UploadFile, File()],
) -> AttachmentRead:
    data = await read_upload(file, attachment_service.MAX_ATTACHMENT_BYTES)
    return await attachment_service.upload_attachment(db, storage, user, parent_type, parent_id, file.filename, data)


@router.get("/{attachment_id}/download")
async def download_attachment(attachment_id: int, db: DbSession, storage: Storage, user: CurrentUser) -> Response:
    """Served only to someone who can see the record the file is attached to, and never rendered by the browser."""
    attachment, data = await attachment_service.read_attachment(db, storage, user, attachment_id)
    return Response(
        content=data,
        media_type=attachment.content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(attachment.filename)}",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment(attachment_id: int, db: DbSession, storage: Storage, user: CurrentUser) -> Response:
    await attachment_service.delete_attachment(db, storage, user, attachment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
