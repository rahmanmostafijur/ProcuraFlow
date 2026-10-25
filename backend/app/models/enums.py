import enum


class POStatus(enum.StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    ORDERED = "ordered"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"
    CANCELLED = "cancelled"


# Orders the business has signed off on; spend metrics count only these, never drafts or cancellations.
COMMITTED_PO_STATUSES = (
    POStatus.APPROVED,
    POStatus.ORDERED,
    POStatus.PARTIALLY_RECEIVED,
    POStatus.RECEIVED,
)


class TaxType(enum.StrEnum):
    VAT = "vat"
    SALES_TAX = "sales_tax"


class DeliveryStatus(enum.StrEnum):
    PENDING = "pending"
    ON_TIME = "on_time"
    DELAYED = "delayed"
    PARTIAL = "partial"


class InventoryTransactionType(enum.StrEnum):
    RECEIVE = "receive"
    ADJUSTMENT = "adjustment"
    PO_RECEIPT = "po_receipt"
    OPENING_BALANCE = "opening_balance"
