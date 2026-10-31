import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import { mockGet, renderWithProviders } from "@/test/render";

import { PortalInvoicesPage } from "./PortalInvoicesPage";
import { buildInvoicePayload, type InvoiceDraft } from "./portalInvoice";

const orderSummary = { id: 12, po_number: "PO-0012" };
const orderDetail = {
  ...orderSummary,
  currency_code: "USD",
  items: [{ product_id: 1, product_name: "Widget", quantity: 10, unit_price: "10.0000" }],
};

function serve() {
  return mockGet({
    "/portal/invoices": { items: [], total: 0, page: 1, page_size: 10, total_pages: 0 },
    "/portal/orders": { items: [orderSummary], total: 1, page: 1, page_size: 100, total_pages: 1 },
    "/portal/orders/12": orderDetail,
  });
}

describe("PortalInvoicesPage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("creates the draft invoice from the order's lines, then uploads the file to it", async () => {
    serve();
    const post = vi
      .spyOn(apiClient, "post")
      .mockImplementation((url) => Promise.resolve({ data: url === "/portal/invoices" ? { id: 40 } : {} }));
    renderWithProviders(<PortalInvoicesPage />);

    fireEvent.click(await screen.findByRole("button", { name: /New invoice/ }));
    fireEvent.change(screen.getByLabelText("Order"), { target: { value: "12" } });
    fireEvent.change(screen.getByLabelText("Invoice number"), { target: { value: "INV-77" } });
    fireEvent.change(screen.getByLabelText("Invoice date"), { target: { value: "2026-11-01" } });
    fireEvent.change(await screen.findByLabelText("Quantity of Widget"), { target: { value: "4" } });
    const file = new File(["%PDF"], "inv.pdf", { type: "application/pdf" });
    fireEvent.change(screen.getByLabelText("Invoice file"), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "Send invoice" }));

    await waitFor(() => expect(post).toHaveBeenCalledTimes(2));
    expect(post.mock.calls[0]).toEqual([
      "/portal/invoices",
      {
        po_id: 12,
        invoice_number: "INV-77",
        invoice_date: "2026-11-01",
        due_date: undefined,
        notes: undefined,
        lines: [{ product_id: 1, quantity: 4, unit_price: "10.0000" }],
      },
    ]);
    expect(post.mock.calls[1][0]).toBe("/portal/invoices/40/files");
    expect((post.mock.calls[1][1] as FormData).get("file")).toBe(file);
  });

  it("explains a missing file instead of sending anything", async () => {
    serve();
    const post = vi.spyOn(apiClient, "post");
    renderWithProviders(<PortalInvoicesPage />);

    fireEvent.click(await screen.findByRole("button", { name: /New invoice/ }));
    fireEvent.change(screen.getByLabelText("Order"), { target: { value: "12" } });
    fireEvent.change(screen.getByLabelText("Invoice number"), { target: { value: "INV-77" } });
    fireEvent.change(screen.getByLabelText("Invoice date"), { target: { value: "2026-11-01" } });
    await screen.findByLabelText("Quantity of Widget");
    fireEvent.click(screen.getByRole("button", { name: "Send invoice" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Attach the invoice as a PDF, PNG or JPEG");
    expect(post).not.toHaveBeenCalled();
  });
});

describe("buildInvoicePayload", () => {
  const draft: InvoiceDraft = {
    orderId: 1,
    invoiceNumber: "A",
    invoiceDate: "2026-11-01",
    dueDate: "",
    notes: "",
    lines: [{ product_id: 1, quantity: "2", unit_price: "5.00" }],
  };
  const file = new File(["x"], "a.pdf");

  it("rejects a due date before the invoice date", () => {
    expect(buildInvoicePayload({ ...draft, dueDate: "2026-10-01" }, file)).toEqual({
      ok: false,
      error: "The due date cannot be before the invoice date",
    });
  });

  it("leaves out lines with quantity 0 and rejects an invoice with none left", () => {
    const zero = { ...draft, lines: [{ product_id: 1, quantity: "0", unit_price: "5.00" }] };
    expect(buildInvoicePayload(zero, file)).toEqual({ ok: false, error: "Bill at least one line" });
  });

  it("rejects a price with too many decimals", () => {
    const bad = { ...draft, lines: [{ product_id: 1, quantity: "1", unit_price: "5.12345" }] };
    expect(buildInvoicePayload(bad, file).ok).toBe(false);
  });
});
