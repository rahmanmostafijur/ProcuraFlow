from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.core.deps import DbSession, require_permission
from app.core.pagination import paginate
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogRead
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/audit-logs", tags=["audit"])

RequireAuditRead = Annotated[User, Depends(require_permission("audit:read"))]


@router.get("", response_model=PaginatedResponse[AuditLogRead])
async def list_audit_logs(
    db: DbSession,
    _: RequireAuditRead,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    entity_type: str | None = None,
) -> PaginatedResponse[AuditLogRead]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)

    items, total, total_pages = await paginate(db, stmt, page, page_size)
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)
