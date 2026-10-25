from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import AttachmentParentType
from app.schemas.person import PersonRead


class AttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parent_type: AttachmentParentType
    parent_id: int
    filename: str
    content_type: str
    size_bytes: int
    uploaded_by: PersonRead
    created_at: datetime
