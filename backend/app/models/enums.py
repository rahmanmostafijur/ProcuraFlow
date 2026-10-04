import enum


class POStatus(str, enum.Enum):
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


class DeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    ON_TIME = "on_time"
    DELAYED = "delayed"
    PARTIAL = "partial"


class InventoryTransactionType(str, enum.Enum):
    RECEIVE = "receive"
    ADJUSTMENT = "adjustment"
    PO_RECEIPT = "po_receipt"
    OPENING_BALANCE = "opening_balance"
