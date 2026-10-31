from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict

from app.core.deps import CurrentUser, DbSession
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    message: str
    is_read: bool
    created_at: datetime


class UnreadCount(BaseModel):
    unread: int


@router.get("", response_model=list[NotificationRead])
async def list_notifications(
    db: DbSession, current_user: CurrentUser, unread_only: bool = Query(default=False)
) -> list[NotificationRead]:
    rows = await notification_service.list_for_user(db, current_user.id, unread_only=unread_only)
    return [NotificationRead.model_validate(row) for row in rows]


@router.get("/unread-count", response_model=UnreadCount)
async def get_unread_count(db: DbSession, current_user: CurrentUser) -> UnreadCount:
    return UnreadCount(unread=await notification_service.unread_count(db, current_user.id))


@router.post("/read-all", response_model=UnreadCount)
async def read_all(db: DbSession, current_user: CurrentUser) -> UnreadCount:
    await notification_service.mark_all_read(db, current_user.id)
    await db.commit()
    return UnreadCount(unread=0)


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def read_one(notification_id: int, db: DbSession, current_user: CurrentUser) -> None:
    if not await notification_service.mark_read(db, current_user.id, notification_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    await db.commit()
