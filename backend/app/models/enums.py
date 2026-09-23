import enum


class POStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    ORDERED = "ordered"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class DeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    ON_TIME = "on_time"
    DELAYED = "delayed"
    PARTIAL = "partial"


class InventoryTransactionType(str, enum.Enum):
    RECEIVE = "receive"
    ADJUSTMENT = "adjustment"
    PO_RECEIPT = "po_receipt"
