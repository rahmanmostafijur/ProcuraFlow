import type { PortalInvoiceInput, PortalOrderLine } from "@/api/portal";

export interface InvoiceLineDraft {
  product_id: number;
  quantity: string;
  unit_price: string;
}

export interface InvoiceDraft {
  orderId: number | null;
  invoiceNumber: string;
  invoiceDate: string;
  dueDate: string;
  notes: string;
  lines: InvoiceLineDraft[];
}

export const MAX_INVOICE_FILE_BYTES = 10 * 1024 * 1024;

/** One draft line per ordered product, pre-filled with the ordered quantity and price. */
export function draftLinesFor(items: PortalOrderLine[]): InvoiceLineDraft[] {
  return items.map((line) => ({
    product_id: line.product_id,
    quantity: String(line.quantity),
    unit_price: line.unit_price,
  }));
}

export type InvoiceResult = { ok: true; input: PortalInvoiceInput } | { ok: false; error: string };

/** Checks what the API checks again, so a typo is explained next to the form rather than after a round trip. */
export function buildInvoicePayload(draft: InvoiceDraft, file: File | null): InvoiceResult {
  if (draft.orderId === null) return { ok: false, error: "Choose the order this invoice is for" };
  if (!draft.invoiceNumber.trim()) return { ok: false, error: "Enter the invoice number" };
  if (!draft.invoiceDate) return { ok: false, error: "Enter the invoice date" };
  if (draft.dueDate && draft.dueDate < draft.invoiceDate) {
    return { ok: false, error: "The due date cannot be before the invoice date" };
  }
  const lines: PortalInvoiceInput["lines"] = [];
  for (const line of draft.lines) {
    const quantity = Number(line.quantity);
    if (!Number.isInteger(quantity) || quantity < 0) return { ok: false, error: "Quantities must be whole numbers" };
    if (quantity === 0) continue;
    if (!/^\d+(\.\d{1,4})?$/.test(line.unit_price.trim())) {
      return { ok: false, error: "Unit prices must be amounts with at most four decimals" };
    }
    lines.push({ product_id: line.product_id, quantity, unit_price: line.unit_price.trim() });
  }
  if (lines.length === 0) return { ok: false, error: "Bill at least one line" };
  if (!file) return { ok: false, error: "Attach the invoice as a PDF, PNG or JPEG" };
  if (file.size > MAX_INVOICE_FILE_BYTES) return { ok: false, error: "That file is larger than 10 MB" };
  return {
    ok: true,
    input: {
      po_id: draft.orderId,
      invoice_number: draft.invoiceNumber.trim(),
      invoice_date: draft.invoiceDate,
      due_date: draft.dueDate || undefined,
      notes: draft.notes.trim() || undefined,
      lines,
    },
  };
}
