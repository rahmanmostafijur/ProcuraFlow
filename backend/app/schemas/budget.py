from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.enums import BudgetChangeType, BudgetTransferStatus
from app.schemas.common import Money
from app.schemas.person import PersonRead

Amount = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=4)]
PositiveAmount = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=4)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20, to_upper=True)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
FiscalYear = Annotated[int, Field(ge=2000, le=2100)]

BudgetHealth = Literal["ok", "warning", "over"]


class CostCentreCreate(BaseModel):
    code: Code
    name: Name
    manager_id: int | None = None


class CostCentreUpdate(BaseModel):
    name: Name | None = None
    manager_id: int | None = None
    is_active: bool | None = None


class CostCentreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    manager_id: int | None
    is_active: bool


class BudgetUpsert(BaseModel):
    cost_centre_id: int
    fiscal_year: FiscalYear
    amount: Amount
    reason: Reason | None = None


class BudgetPositionRead(BaseModel):
    budget_id: int
    cost_centre_id: int
    cost_centre_code: str
    cost_centre_name: str
    fiscal_year: int
    budget: Money
    spent: Money
    committed: Money
    remaining: Money
    # Spent plus committed as a share of the budget; empty when the budget is zero.
    utilisation_percent: Decimal | None
    health: BudgetHealth


class BudgetChangeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    change_type: BudgetChangeType
    old_amount: Money | None
    new_amount: Money
    reason: str | None
    transfer_id: int | None
    changed_by: int
    created_at: datetime


class TransferCreate(BaseModel):
    from_budget_id: int
    to_budget_id: int
    amount: PositiveAmount
    reason: Reason


class TransferDecision(BaseModel):
    comment: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None


class TransferRead(BaseModel):
    id: int
    from_budget_id: int
    to_budget_id: int
    from_label: str
    to_label: str
    amount: Money
    reason: str
    status: BudgetTransferStatus
    requested_by: PersonRead
    decided_by: PersonRead | None
    decided_at: datetime | None
    decision_comment: str | None
    created_at: datetime
