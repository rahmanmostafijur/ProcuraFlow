from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.core.deps import DbSession, require_permission
from app.core.uploads import download_response
from app.models.user import User
from app.schemas.payment_file import PaymentFileRead
from app.services import payment_file_service
from app.services.today import Today
from app.storage import StorageBackend, get_storage

router = APIRouter(prefix="/payment-runs/{run_id}/file", tags=["payment-files"])

RequirePaymentExport = Annotated[User, Depends(require_permission("payment:export"))]
Storage = Annotated[StorageBackend, Depends(get_storage)]


@router.post("", response_model=PaymentFileRead)
async def export_file(
    run_id: int, response: Response, db: DbSession, storage: Storage, actor: RequirePaymentExport, today: Today
) -> PaymentFileRead:
    """Generate the bank file of a released run. The first call creates it (201); later calls return the same file."""
    file, created = await payment_file_service.generate_file(db, storage, actor, run_id, today)
    response.status_code = 201 if created else 200
    return file


@router.get("", response_model=PaymentFileRead)
async def file_info(run_id: int, db: DbSession, _: RequirePaymentExport) -> PaymentFileRead:
    return await payment_file_service.get_file_info(db, run_id)


@router.get("/download")
async def download_file(run_id: int, db: DbSession, storage: Storage, actor: RequirePaymentExport) -> Response:
    """The stored file, byte for byte as it was generated. Each download is audited."""
    file, data = await payment_file_service.read_file(db, storage, actor, run_id)
    return download_response(data, file.content_type, file.filename)
