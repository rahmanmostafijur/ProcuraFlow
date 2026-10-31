from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status

from app.core.deps import DbSession, require_permission
from app.core.uploads import download_response, read_upload
from app.models.enums import SupplierDocumentStatus, SupplierDocumentType
from app.models.user import User
from app.schemas.supplier_document import ExpiringDocumentRead, SupplierDocumentRead
from app.services import supplier_document_service
from app.services.supplier_document_service import DocumentUpload
from app.services.today import Today
from app.storage import StorageBackend, get_storage

router = APIRouter(tags=["supplier-documents"])

RequireSupplierWrite = Annotated[User, Depends(require_permission("supplier:write"))]
Storage = Annotated[StorageBackend, Depends(get_storage)]


@router.get("/supplier-documents/expiring", response_model=list[ExpiringDocumentRead])
async def expiring_documents(
    db: DbSession,
    _: RequireSupplierWrite,
    today: Today,
    state: Annotated[
        SupplierDocumentStatus | None, Query(alias="status", description="expiring_soon or expired; omit for both")
    ] = None,
) -> list[ExpiringDocumentRead]:
    """Documents of active suppliers that expire within 30 days or already have, soonest first."""
    wanted = (
        frozenset({state})
        if state in (SupplierDocumentStatus.EXPIRING_SOON, SupplierDocumentStatus.EXPIRED)
        else frozenset({SupplierDocumentStatus.EXPIRING_SOON, SupplierDocumentStatus.EXPIRED})
    )
    return await supplier_document_service.documents_needing_attention(db, today, wanted)


@router.get("/suppliers/{supplier_id}/documents", response_model=list[SupplierDocumentRead])
async def list_documents(
    supplier_id: int, db: DbSession, _: RequireSupplierWrite, today: Today
) -> list[SupplierDocumentRead]:
    return await supplier_document_service.list_documents(db, supplier_id, today)


@router.post(
    "/suppliers/{supplier_id}/documents", response_model=SupplierDocumentRead, status_code=status.HTTP_201_CREATED
)
async def upload_document(
    supplier_id: int,
    db: DbSession,
    storage: Storage,
    actor: RequireSupplierWrite,
    today: Today,
    document_type: Annotated[SupplierDocumentType, Form()],
    file: Annotated[UploadFile, File()],
    issue_date: Annotated[date | None, Form()] = None,
    expiry_date: Annotated[date | None, Form()] = None,
) -> SupplierDocumentRead:
    data = await read_upload(file, supplier_document_service.MAX_DOCUMENT_BYTES)
    upload = DocumentUpload(document_type, issue_date, expiry_date, file.filename, data)
    return await supplier_document_service.upload_document(db, storage, actor, supplier_id, upload, today)


@router.get("/suppliers/{supplier_id}/documents/{document_id}/download")
async def download_document(
    supplier_id: int, document_id: int, db: DbSession, storage: Storage, _: RequireSupplierWrite
) -> Response:
    document, data = await supplier_document_service.read_document_file(db, storage, supplier_id, document_id)
    return download_response(data, document.content_type, document.filename)


@router.delete("/suppliers/{supplier_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    supplier_id: int, document_id: int, db: DbSession, storage: Storage, actor: RequireSupplierWrite
) -> Response:
    await supplier_document_service.delete_document(db, storage, actor, supplier_id, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
