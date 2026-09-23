from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import DeliveryStatus


class DeliveryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    po_id: int
    expected_date: date | None
    actual_date: date | None
    status: DeliveryStatus
    ordered_quantity: int
    received_quantity: int
    created_at: datetime
    updated_at: datetime
