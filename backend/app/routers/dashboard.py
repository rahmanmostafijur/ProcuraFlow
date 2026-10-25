from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser, DbSession, require_permission
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.dashboard import DashboardSummary, MonthlyTrendPoint, RecentActivityItem
from app.services import metrics_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# The activity feed is a view of the audit log, so it carries the audit log's permission.
RequireAuditRead = Annotated[User, Depends(require_permission("audit:read"))]


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(db: DbSession, _: CurrentUser) -> DashboardSummary:
    return await metrics_service.dashboard_summary(db)


@router.get("/monthly-trends", response_model=list[MonthlyTrendPoint])
async def get_monthly_trends(
    db: DbSession, _: CurrentUser, months: int = Query(6, ge=1, le=24)
) -> list[MonthlyTrendPoint]:
    context = await metrics_service.get_context(db)
    points = await metrics_service.committed_spend_by_month(db, context, months)
    return [
        MonthlyTrendPoint(month=point.month, total_spend=point.total_spend, order_count=point.order_count)
        for point in points
    ]


@router.get("/recent-activity", response_model=list[RecentActivityItem])
async def get_recent_activity(
    db: DbSession, _: RequireAuditRead, limit: int = Query(10, ge=1, le=50)
) -> list[RecentActivityItem]:
    stmt = select(AuditLog).options(selectinload(AuditLog.user)).order_by(AuditLog.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    logs = result.scalars().all()
    return [
        RecentActivityItem(
            id=log.id,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            created_at=log.created_at,
            user_name=log.user.full_name if log.user else None,
        )
        for log in logs
    ]
