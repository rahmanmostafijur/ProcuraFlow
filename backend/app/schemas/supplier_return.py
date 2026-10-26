from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.enums import ReturnResolution, ReturnStatus
from app.schemas.person import PersonRead

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class SupplierReturnCreate(BaseModel):
    po_id: int
    product_id: int
    quantity: int = Field(gt=0)
    reason: Reason
    resolution: ReturnResolution
    note: Note | None = None


class SupplierReturnStatusChange(BaseModel):
    status: ReturnStatus
    note: Note | None = None


class SupplierReturnRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    po_id: int
    po_number: str
    supplier_id: int
    supplier_name: str
    product_id: int
    product_sku: str
    product_name: str
    quantity: int
    reason: str
    resolution: ReturnResolution
    status: ReturnStatus
    created_by: PersonRead
    resolved_at: datetime | None
    note: str | None
    created_at: datetime
