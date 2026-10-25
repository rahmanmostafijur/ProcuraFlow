import type { PurchaseOrder, PurchaseRequest, QueueItem, RequestLine } from "@/api/types";

export const person = (id: number, name: string) => ({ id, full_name: name });

export function queueItem(overrides: Partial<QueueItem> = {}): QueueItem {
  return {
    document_type: "purchase_request",
    document_id: 5,
    po_id: null,
    label: "REQ-0005",
    title: "Laptops for new hires",
    amount_base: "4800.00",
    requester: person(2, "Rita Requester"),
    submitted_at: "2026-10-20T09:00:00Z",
    step_order: 2,
    steps_total: 3,
    rule_name: null,
    on_behalf_of: null,
    ...overrides,
  };
}

export function requestLine(overrides: Partial<RequestLine> = {}): RequestLine {
  return {
    id: 11,
    description: "Laptop",
    catalog_item_id: null,
    product_id: null,
    supplier_id: null,
    quantity: 2,
    unit: "unit",
    estimated_unit_price: "2400.0000",
    line_total: "4800.00",
    converted_po_id: null,
    ...overrides,
  };
}

export function purchaseRequest(overrides: Partial<PurchaseRequest> = {}): PurchaseRequest {
  return {
    id: 5,
    request_number: "REQ-0005",
    requester: person(1, "Me Myself"),
    title: "Laptops for new hires",
    notes: null,
    cost_centre_id: null,
    currency_code: "USD",
    needed_by: null,
    status: "draft",
    estimated_total: "4800.00",
    base_estimated_total: null,
    submitted_at: null,
    decided_at: null,
    rejection_reason: null,
    created_at: "2026-10-20T09:00:00Z",
    updated_at: "2026-10-20T09:00:00Z",
    lines: [requestLine()],
    ...overrides,
  };
}

export function purchaseOrder(overrides: Partial<PurchaseOrder> = {}): PurchaseOrder {
  return {
    id: 7,
    po_number: "PO-0007",
    supplier: {
      id: 3,
      name: "Acme Supplies",
      contact_name: null,
      email: null,
      phone: null,
      address: null,
      country_code: null,
      tax_id: null,
      currency_code: null,
      payment_terms_days: null,
      is_active: true,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    },
    status: "submitted",
    currency_code: "USD",
    cost_centre_id: 4,
    purchase_request_id: null,
    version: 1,
    expected_delivery_date: null,
    notes: null,
    items: [
      {
        id: 1,
        product_id: 9,
        quantity: 10,
        unit_price: "5.0000",
        received_quantity: 0,
        tax_rate_id: null,
        tax_name: null,
        tax_percent: "0",
        tax_inclusive: false,
        reverse_charge: false,
        line_net: "50.00",
        line_tax: "0.00",
        line_total: "50.00",
      },
    ],
    creator: {
      id: 2,
      email: "creator@example.com",
      full_name: "Casey Creator",
      is_active: true,
      role: { id: 1, name: "purchasing_officer", description: null, permissions: [] },
      created_at: "2026-01-01T00:00:00Z",
    },
    approver: null,
    approved_at: null,
    created_at: "2026-10-20T09:00:00Z",
    updated_at: "2026-10-20T09:00:00Z",
    subtotal: "50.00",
    tax_total: "0.00",
    grand_total: "50.00",
    exchange_rate: null,
    base_subtotal: null,
    base_tax_total: null,
    base_grand_total: null,
    total: "50.00",
    ...overrides,
  };
}
