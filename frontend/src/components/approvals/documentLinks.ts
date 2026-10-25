import type { ApprovalDocumentType } from "@/api/types";

export const DOCUMENT_TYPE_LABELS: Record<ApprovalDocumentType, string> = {
  purchase_request: "Request",
  purchase_order: "Purchase order",
  purchase_order_amendment: "Order change",
  invoice_exception: "Invoice exception",
};

/** Where to read a document waiting for approval. An amendment opens the order it changes (``poId``). */
export function documentLink(
  documentType: ApprovalDocumentType,
  documentId: number,
  poId: number | null = null,
): string | null {
  switch (documentType) {
    case "purchase_request":
      return `/requests/${documentId}`;
    case "purchase_order":
      return `/purchase-orders/${documentId}`;
    case "purchase_order_amendment":
      return poId === null ? "/purchase-orders" : `/purchase-orders/${poId}`;
    case "invoice_exception":
      return null;
  }
}
