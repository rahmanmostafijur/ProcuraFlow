from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models.enums import ApprovalDocumentType, ApprovalStepStatus
from app.schemas.common import Money
from app.schemas.person import PersonRead

Amount = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=4)]
RuleName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
Comment = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]
MAX_STEPS_PER_RULE = 5


class ApprovalRuleStepWrite(BaseModel):
    approver_role_id: int


class ApprovalRuleCreate(BaseModel):
    name: RuleName
    document_type: ApprovalDocumentType
    min_amount: Amount = Decimal(0)
    # Empty means no upper limit.
    max_amount: Amount | None = None
    is_active: bool = True
    steps: list[ApprovalRuleStepWrite] = Field(min_length=1, max_length=MAX_STEPS_PER_RULE)

    @model_validator(mode="after")
    def _band_is_not_empty(self) -> "ApprovalRuleCreate":
        if self.max_amount is not None and self.max_amount <= self.min_amount:
            raise ValueError("The upper limit must be greater than the lower limit")
        return self


class ApprovalRuleUpdate(BaseModel):
    name: RuleName | None = None
    min_amount: Amount | None = None
    max_amount: Amount | None = None
    is_active: bool | None = None
    # When sent, replaces the whole chain of steps.
    steps: list[ApprovalRuleStepWrite] | None = Field(default=None, min_length=1, max_length=MAX_STEPS_PER_RULE)


class ApprovalRuleStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    step_order: int
    approver_role_id: int


class ApprovalRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    document_type: ApprovalDocumentType
    min_amount: Money
    max_amount: Money | None
    is_active: bool
    steps: list[ApprovalRuleStepRead]


class ApprovalStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    round: int
    step_order: int
    approver_role_id: int | None
    required_permission: str | None
    rule_name: str | None
    amount_base: Money
    status: ApprovalStepStatus
    decided_by: int | None
    on_behalf_of: int | None
    decided_at: datetime | None
    comment: str | None


class ApprovalTimelineStep(ApprovalStepRead):
    """A step with the names a screen needs: who may decide it and who did."""

    approver_label: str
    decided_by_person: PersonRead | None
    on_behalf_of_person: PersonRead | None


class DecisionRequest(BaseModel):
    comment: Comment | None = None


class RejectionRequest(BaseModel):
    comment: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class QueueItem(BaseModel):
    document_type: ApprovalDocumentType
    document_id: int
    # The purchase order an order or amendment belongs to, so a screen can link straight to it.
    po_id: int | None
    label: str
    title: str
    amount_base: Money
    requester: PersonRead
    submitted_at: datetime | None
    step_order: int
    steps_total: int
    rule_name: str | None
    # Set when the user can decide this only because someone delegated it to them.
    on_behalf_of: PersonRead | None


class QueuePage(BaseModel):
    items: list[QueueItem]
    total: int


class ApprovalLimitWrite(BaseModel):
    user_id: int
    document_type: ApprovalDocumentType
    max_amount: Amount


class ApprovalLimitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    document_type: ApprovalDocumentType
    max_amount: Money
    updated_at: datetime


class DelegationCreate(BaseModel):
    delegate_id: int
    starts_on: date
    ends_on: date
    # Only people who manage approvals may set this up for someone else.
    delegator_id: int | None = None

    @model_validator(mode="after")
    def _dates_in_order(self) -> "DelegationCreate":
        if self.ends_on < self.starts_on:
            raise ValueError("The delegation cannot end before it starts")
        return self


class DelegationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    delegator: PersonRead
    delegate: PersonRead
    starts_on: date
    ends_on: date
    revoked_at: datetime | None
    created_at: datetime
