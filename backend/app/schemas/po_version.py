from datetime import date, datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.enums import AmendmentStatus
from app.schemas.person import PersonRead
from app.schemas.purchase_order import POItemList


class PurchaseOrderAmend(BaseModel):
    """What an ordered purchase order should look like after the change, and why it is being changed."""

    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    items: POItemList | None = Field(default=None, min_length=1)
    expected_delivery_date: date | None = None
    notes: str | None = Field(default=None, max_length=5000)


class PurchaseOrderVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    po_id: int
    version: int
    status: AmendmentStatus
    reason: str
    created_by_person: PersonRead
    created_at: datetime
    decided_at: datetime | None
    # What changed from the version before, one readable entry per field or line.
    changes: list[dict[str, Any]]
    snapshot: dict[str, Any]
