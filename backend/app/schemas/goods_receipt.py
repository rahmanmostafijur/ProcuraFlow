from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import ReceiptCondition
from app.schemas.person import PersonRead


class GoodsReceiptLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    delivered_quantity: int
    accepted_quantity: int
    rejected_quantity: int
    condition: ReceiptCondition
    note: str | None


class GoodsReceiptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    po_id: int
    received_by: int
    receiver: PersonRead
    received_at: datetime
    note: str | None
    lines: list[GoodsReceiptLineRead]
