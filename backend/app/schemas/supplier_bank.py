from datetime import datetime
from typing import Annotated, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints, model_validator

from app.core.bank_validation import (
    ACCOUNT_NUMBER_PATTERN,
    BIC_PATTERN,
    compact,
    is_valid_iban,
    is_valid_routing_number,
)
from app.schemas.person import PersonRead
from app.schemas.supplier import CountryCodeStr


def _blank_to_none(value: object) -> object:
    return None if isinstance(value, str) and not value.strip() else value


def _compact(value: object) -> object:
    return compact(value) if isinstance(value, str) else value


OptionalIdentifier = Annotated[str | None, BeforeValidator(_blank_to_none), BeforeValidator(_compact)]
AccountName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=140)]


class BankDetailsInput(BaseModel):
    """What a change request carries. Identifiers are checked here, so a typo is refused when it is typed."""

    bank_account_name: AccountName
    bank_country: CountryCodeStr
    iban: OptionalIdentifier = None
    bic: OptionalIdentifier = None
    bank_account_number: OptionalIdentifier = None
    routing_number: OptionalIdentifier = None

    @model_validator(mode="after")
    def _check_identifiers(self) -> Self:
        if not self.iban and not self.bank_account_number:
            raise ValueError("Give an IBAN or a bank account number")
        if self.iban:
            if not is_valid_iban(self.iban):
                raise ValueError("The IBAN is not valid (check the digits)")
            if self.iban[:2] != self.bank_country:
                raise ValueError("The IBAN does not belong to the bank country")
        if self.bic and not BIC_PATTERN.fullmatch(self.bic):
            raise ValueError("The BIC must be 8 or 11 letters and digits")
        if self.bank_account_number and not ACCOUNT_NUMBER_PATTERN.fullmatch(self.bank_account_number):
            raise ValueError("The bank account number may only contain letters and digits")
        if self.routing_number:
            if not is_valid_routing_number(self.routing_number):
                raise ValueError("The routing number is not a valid 9-digit ABA number")
            if not self.bank_account_number:
                raise ValueError("A routing number needs a bank account number")
        return self


class BankDecision(BaseModel):
    comment: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None


class BankDetailsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    supplier_id: int
    status: str
    bank_account_name: str | None
    bank_country: str | None
    iban: str | None
    bic: str | None
    bank_account_number: str | None
    routing_number: str | None
    requested_by: PersonRead
    requested_at: datetime
    decided_by: PersonRead | None
    decided_at: datetime | None
    decision_comment: str | None
    superseded_at: datetime | None


class BankDetailsOverview(BaseModel):
    current: BankDetailsRead | None
    pending: BankDetailsRead | None
    # Superseded and rejected versions, newest first.
    history: list[BankDetailsRead] = Field(default_factory=list)
