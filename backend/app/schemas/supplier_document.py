from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import SupplierDocumentStatus, SupplierDocumentType
from app.schemas.person import PersonRead


class SupplierDocumentRead(BaseModel):
    id: int
    supplier_id: int
    document_type: SupplierDocumentType
    issue_date: date | None
    expiry_date: date | None
    # Worked out from the expiry date and today's date for this response; never stored.
    status: SupplierDocumentStatus
    days_until_expiry: int | None
    filename: str
    content_type: str
    size_bytes: int
    uploaded_by: PersonRead
    created_at: datetime


class ExpiringDocumentRead(SupplierDocumentRead):
    supplier_name: str
