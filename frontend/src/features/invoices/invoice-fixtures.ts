import type { Invoice, InvoiceLine, InvoiceSummary } from "@/api/supplierInvoices";

export function invoiceLine(overrides: Partial<InvoiceLine> = {}): InvoiceLine {
  return {
    id: 1,
    po_item_id: 10,
    product_id: 5,
    description: "Laptop stand",
    quantity: 2,
    unit_price: "50.0000",
    tax_rate_id: null,
    tax_name: null,
    tax_percent: "0",
    tax_inclusive: false,
    reverse_charge: false,
    line_net: "100.00",
    line_tax: "0.00",
    line_total: "100.00",
    ...overrides,
  };
}

export function invoice(overrides: Partial<Invoice> = {}): Invoice {
  return {
    id: 3,
    supplier: { id: 2, name: "Zeta Supplies" },
    purchase_order: { id: 7, po_number: "PO-0007" },
    invoice_number: "INV-0003",
    invoice_date: "2026-01-05",
    due_date: "2026-02-04",
    currency_code: "USD",
    subtotal: "100.00",
    tax_total: "0.00",
    grand_total: "100.00",
    paid_total: "0.00",
    open_amount: "100.00",
    status: "matched",
    match_mode: "three_way",
    tolerance_percent: "2.0",
    exception_reasons: [],
    notes: null,
    created_by: 99,
    creator: { id: 99, full_name: "Clerk Colleague" },
    submitted_at: "2026-01-06T09:00:00Z",
    approved_by: null,
    approver: null,
    approved_at: null,
    hold_reason: null,
    void_reason: null,
    rejection_reason: null,
    exchange_rate: null,
    base_subtotal: null,
    base_tax_total: null,
    base_grand_total: null,
    created_at: "2026-01-05T09:00:00Z",
    updated_at: "2026-01-06T09:00:00Z",
    lines: [invoiceLine()],
    ...overrides,
  };
}

export function invoiceSummary(overrides: Partial<InvoiceSummary> = {}): InvoiceSummary {
  // A list row is an invoice without its lines; the extra field is harmless to the page.
  return invoice(overrides);
}
