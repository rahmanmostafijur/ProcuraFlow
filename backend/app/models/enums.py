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


class ApprovalDocumentType(enum.StrEnum):
    PURCHASE_REQUEST = "purchase_request"
    PURCHASE_ORDER = "purchase_order"
    PURCHASE_ORDER_AMENDMENT = "purchase_order_amendment"
    INVOICE_EXCEPTION = "invoice_exception"


class ApprovalStepStatus(enum.StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    # Never decided: the document was rejected or cancelled before this step was reached.
    SKIPPED = "skipped"


class PurchaseRequestStatus(enum.StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    CONVERTED = "converted"
    CANCELLED = "cancelled"


class BudgetTransferStatus(enum.StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class BudgetChangeType(enum.StrEnum):
    CREATED = "created"
    ADJUSTED = "adjusted"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"


class AttachmentParentType(enum.StrEnum):
    PURCHASE_REQUEST = "purchase_request"
    PURCHASE_ORDER = "purchase_order"


class AmendmentStatus(enum.StrEnum):
    # The state of a purchase order as it was when the version was made.
    APPLIED = "applied"
    # Raises the total, so it waits for approval before it changes the order.
    PENDING_APPROVAL = "pending_approval"
    REJECTED = "rejected"


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
