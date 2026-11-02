import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import type { InvoiceSummary } from "@/api/supplierInvoices";
import { mockGet, renderWithProviders } from "@/test/render";

import { PaymentRunsPage } from "./PaymentRunsPage";

function invoice(id: number, currency: string, openAmount: string): InvoiceSummary {
  return {
    id,
    supplier: { id: 10 + id, name: `Supplier ${id}` },
    invoice_number: `INV-${id}`,
    due_date: "2026-12-01",
    currency_code: currency,
    open_amount: openAmount,
    status: "approved",
  } as InvoiceSummary;
}

const emptyRuns = { items: [], total: 0, page: 1, page_size: 10, total_pages: 1 };

function setup(invoices: InvoiceSummary[], permissions = ["invoice:read", "payment:write"]) {
  mockGet({
    "/payment-runs": emptyRuns,
    "/supplier-invoices": { ...emptyRuns, items: invoices, total: invoices.length },
  });
  return renderWithProviders(<PaymentRunsPage />, { permissions });
}

describe("NewPaymentRunModal", () => {
  afterEach(() => vi.restoreAllMocks());

  it("hides the action without payment:write", async () => {
    setup([], ["invoice:read"]);
    await screen.findByText("No payment runs");
    expect(screen.queryByRole("button", { name: "New payment run" })).toBeNull();
  });

  it("lists payable invoices, selects all and totals them", async () => {
    setup([invoice(1, "EUR", "100.00"), invoice(2, "EUR", "250.50")]);
    fireEvent.click(await screen.findByRole("button", { name: "New payment run" }));

    expect(await screen.findByText("INV-1")).toBeTruthy();
    expect(screen.getByText("INV-2")).toBeTruthy();
    fireEvent.click(screen.getByRole("checkbox", { name: "Select all invoices" }));
    expect(screen.getByText("2 selected")).toBeTruthy();
    expect(screen.getByText(/350\.50/, { selector: "dd" })).toBeTruthy();
  });

  it("sends the selected invoice ids", async () => {
    setup([invoice(1, "EUR", "100.00"), invoice(2, "EUR", "250.50")]);
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: { id: 9, number: "PAY-2026-00009" } });
    fireEvent.click(await screen.findByRole("button", { name: "New payment run" }));

    fireEvent.click(await screen.findByRole("checkbox", { name: "Select invoice INV-2" }));
    fireEvent.click(screen.getByRole("button", { name: "Create payment run" }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/payment-runs", { invoice_ids: [2], method: "bank_transfer" }),
    );
    expect(await screen.findByText("Payment run PAY-2026-00009 created")).toBeTruthy();
  });

  it("asks for a selection and refuses mixed currencies", async () => {
    setup([invoice(1, "EUR", "100.00"), invoice(2, "USD", "50.00")]);
    const post = vi.spyOn(apiClient, "post");
    fireEvent.click(await screen.findByRole("button", { name: "New payment run" }));

    fireEvent.click(await screen.findByRole("button", { name: "Create payment run" }));
    expect(await screen.findByText("Select at least one invoice")).toBeTruthy();

    fireEvent.click(screen.getByRole("checkbox", { name: "Select all invoices" }));
    fireEvent.click(screen.getByRole("button", { name: "Create payment run" }));
    expect(await screen.findByText(/pays one currency/)).toBeTruthy();
    expect(post).not.toHaveBeenCalled();
  });
});
