from datetime import datetime

from pydantic import BaseModel

from app.models.enums import PaymentFileFormat
from app.schemas.common import Money
from app.schemas.person import PersonRead


class PaymentFileRead(BaseModel):
    id: int
    run_id: int
    run_number: str
    file_format: PaymentFileFormat
    filename: str
    content_type: str
    size_bytes: int
    # SHA-256 of the stored file, so the bank file can be checked against what was audited.
    sha256: str
    currency_code: str
    transaction_count: int
    total: Money
    created_by: PersonRead
    created_at: datetime
