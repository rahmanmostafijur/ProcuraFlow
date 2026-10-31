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
    SUPPLIER_INVOICE = "supplier_invoice"


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


class ReceiptCondition(enum.StrEnum):
    GOOD = "good"
    DAMAGED = "damaged"
    WRONG_ITEM = "wrong_item"
    OTHER = "other"


class ReturnResolution(enum.StrEnum):
    REPLACE = "replace"
    CREDIT_NOTE = "credit_note"
    REPAIR = "repair"


class ReturnStatus(enum.StrEnum):
    OPEN = "open"
    SENT = "sent"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class InvoiceStatus(enum.StrEnum):
    DRAFT = "draft"
    MATCHED = "matched"
    EXCEPTION = "exception"
    APPROVED = "approved"
    ON_HOLD = "on_hold"
    PAID = "paid"
    VOID = "void"


class InvoiceMatchMode(enum.StrEnum):
    # Price and quantity against what was received (accepted units only).
    THREE_WAY = "three_way"
    # Price and quantity against what was ordered.
    TWO_WAY = "two_way"


class PaymentMethod(enum.StrEnum):
    BANK_TRANSFER = "bank_transfer"
    CARD = "card"
    CHEQUE = "cheque"


class PaymentRunStatus(enum.StrEnum):
    DRAFT = "draft"
    RELEASED = "released"
    CANCELLED = "cancelled"


class MatchReasonCode(enum.StrEnum):
    PRICE_VARIANCE = "PRICE_VARIANCE"
    QUANTITY_EXCEEDS_RECEIVED = "QUANTITY_EXCEEDS_RECEIVED"
    QUANTITY_EXCEEDS_ORDERED = "QUANTITY_EXCEEDS_ORDERED"
    TOTAL_EXCEEDS_ORDER = "TOTAL_EXCEEDS_ORDER"
    DUPLICATE_INVOICE = "DUPLICATE_INVOICE"
    UNKNOWN_LINE = "UNKNOWN_LINE"


class SupplierDocumentType(enum.StrEnum):
    W9 = "w9"
    VAT_CERTIFICATE = "vat_certificate"
    INSURANCE = "insurance"
    ISO_CERTIFICATE = "iso_certificate"
    BANK_LETTER = "bank_letter"


class SupplierDocumentStatus(enum.StrEnum):
    # Computed from the expiry date and today's date whenever it is read; never stored.
    VALID = "valid"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"


class BankDetailsStatus(enum.StrEnum):
    # A change waiting for a second person; it changes nothing until approved.
    PENDING = "pending"
    CURRENT = "current"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class PaymentFileFormat(enum.StrEnum):
    SEPA_PAIN001 = "sepa_pain001"
    NACHA_ACH = "nacha_ach"
