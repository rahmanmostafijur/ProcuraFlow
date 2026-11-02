import type { ApprovalDocumentType, QueueItem } from "@/api/types";
import type { ExceptionReason, Invoice, InvoiceStatus, MatchReasonCode, PaymentMethod } from "@/api/supplierInvoices";
import type { LifecycleStep, StepState } from "@/components/ui/LifecycleStepper";

import { isInQueue } from "../purchase-orders/approval";

export const INVOICE_STATUS_OPTIONS: { value: InvoiceStatus | ""; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "draft", label: "Draft" },
  { value: "matched", label: "Matched" },
  { value: "exception", label: "Exception" },
  { value: "approved", label: "Approved" },
  { value: "on_hold", label: "On hold" },
  { value: "paid", label: "Paid" },
  { value: "void", label: "Void" },
];

export const PAYMENT_METHOD_LABELS: Record<PaymentMethod, string> = {
  bank_transfer: "Bank transfer",
  card: "Card",
  cheque: "Cheque",
};

export const REASON_LABELS: Record<MatchReasonCode, string> = {
  PRICE_VARIANCE: "Price differs from the order",
  QUANTITY_EXCEEDS_RECEIVED: "More than was received",
  QUANTITY_EXCEEDS_ORDERED: "More than was ordered",
  TOTAL_EXCEEDS_ORDER: "Total above the order",
  DUPLICATE_INVOICE: "Possible duplicate",
  UNKNOWN_LINE: "Not on the order",
};

const EXCEPTION_DOCUMENT: ApprovalDocumentType = "invoice_exception";
const VOIDABLE: InvoiceStatus[] = ["draft", "matched", "exception", "on_hold", "approved"];
const HOLDABLE: InvoiceStatus[] = ["matched", "exception", "approved"];

export interface InvoiceViewer {
  id: number;
  hasPermission: (code: string) => boolean;
}

export interface InvoiceActionFlags {
  canSubmit: boolean;
  canDecide: boolean;
  canHold: boolean;
  canRelease: boolean;
  canVoid: boolean;
  canPay: boolean;
  /** A creator holding the approve permission who cannot approve a matched invoice of their own. */
  needsAnotherApprover: boolean;
}

/** What this user may do to this invoice now: permission and status together, mirroring the API's own checks. */
export function invoiceActions(
  invoice: Invoice,
  viewer: InvoiceViewer,
  queue: readonly QueueItem[] | undefined,
): InvoiceActionFlags {
  const { status } = invoice;
  const canWrite = viewer.hasPermission("invoice:write");
  const canApprove = viewer.hasPermission("invoice:approve");
  const isCreator = invoice.created_by === viewer.id;
  const decidesMatched = status === "matched" && canApprove && !isCreator;
  const decidesException = status === "exception" && isInQueue(queue, EXCEPTION_DOCUMENT, invoice.id);
  return {
    canSubmit: status === "draft" && canWrite,
    canDecide: decidesMatched || decidesException,
    canHold: canApprove && HOLDABLE.includes(status),
    canRelease: canApprove && status === "on_hold",
    canVoid: canWrite && VOIDABLE.includes(status) && Number(invoice.paid_total) === 0,
    canPay: viewer.hasPermission("payment:write") && status === "approved" && Number(invoice.open_amount) > 0,
    needsAnotherApprover: status === "matched" && canApprove && isCreator,
  };
}

const FLOW = ["Draft", "Matching", "Approved", "Paid"] as const;
const REACHED: Record<InvoiceStatus, number> = {
  draft: 0,
  matched: 1,
  exception: 1,
  approved: 2,
  paid: 3,
  on_hold: 1,
  void: -1,
};

/** Draft, matching, approved, paid. A held invoice shows only the draft as done; void shows nothing reached. */
export function invoiceSteps(invoice: Invoice): LifecycleStep[] {
  const reached = REACHED[invoice.status];
  return FLOW.map((label, position) => {
    const state: StepState =
      invoice.status === "paid"
        ? "done"
        : position < reached
          ? "done"
          : position === reached && invoice.status !== "on_hold"
            ? "current"
            : "upcoming";
    const stepLabel =
      position === 1
        ? invoice.status === "exception"
          ? "Exception"
          : invoice.status === "matched"
            ? "Matched"
            : label
        : label;
    return { id: label.toLowerCase(), label: stepLabel, state };
  });
}

/** Reasons that belong to one invoice line (1-based), and those about the invoice as a whole. */
export function reasonsForLine(reasons: readonly ExceptionReason[], line: number): ExceptionReason[] {
  return reasons.filter((reason) => reason.line === line);
}

export function reasonsForInvoice(reasons: readonly ExceptionReason[]): ExceptionReason[] {
  return reasons.filter((reason) => reason.line === null);
}
