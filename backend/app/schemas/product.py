from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.category import CategoryRead
from app.schemas.supplier import SupplierRead


class ProductBase(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    category_id: int | None = None
    unit: str = Field(default="unit", max_length=32)
    cost: Decimal = Field(ge=0)
    minimum_stock: int = Field(ge=0, default=0)
    supplier_id: int | None = None


class ProductCreate(ProductBase):
    # New products start at zero stock; opening stock is booked through the inventory ledger.
    # Forbidding unknown fields makes clients that still send current_stock fail loudly.
    model_config = ConfigDict(extra="forbid")


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category_id: int | None = None
    unit: str | None = Field(default=None, max_length=32)
    cost: Decimal | None = Field(default=None, ge=0)
    minimum_stock: int | None = Field(default=None, ge=0)
    supplier_id: int | None = None
    is_active: bool | None = None


class ProductRead(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    current_stock: int
    is_active: bool
    category: CategoryRead | None = None
    supplier: SupplierRead | None = None
    created_at: datetime
    updated_at: datetime
