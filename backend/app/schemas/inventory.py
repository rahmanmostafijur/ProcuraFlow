from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import InventoryTransactionType


class InventoryAdjustmentCreate(BaseModel):
    product_id: int
    quantity_delta: int
    reason: str = Field(min_length=1, max_length=255)


class OpeningBalanceCreate(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)
    reason: str | None = Field(default=None, min_length=1, max_length=255)


class InventoryTransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    type: InventoryTransactionType
    quantity_delta: int
    resulting_stock: int
    reference_po_id: int | None
    reason: str | None
    created_by: int
    created_at: datetime
