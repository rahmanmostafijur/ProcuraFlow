import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockGet, renderWithProviders } from "@/test/render";

import { invoiceSummary } from "./invoice-fixtures";
import { InvoicesPage } from "./InvoicesPage";

const totals = {
  by_status: { matched: 1 },
  needing_attention: 1,
  payables_outstanding: "100.00",
  payables_overdue: "0.00",
};

function page(items: ReturnType<typeof invoiceSummary>[]) {
  return { items, total: items.length, page: 1, page_size: 20, total_pages: 1, totals };
}

describe("InvoicesPage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("renders a row per invoice with supplier, status and amounts", async () => {
    mockGet({
      "/supplier-invoices": page([
        invoiceSummary(),
        invoiceSummary({ id: 4, invoice_number: "INV-0004", status: "exception", grand_total: "250.00" }),
      ]),
    });
    renderWithProviders(<InvoicesPage />, { permissions: ["invoice:read"] });

    expect(await screen.findByText("INV-0003")).toBeInTheDocument();
    expect(screen.getByText("INV-0004")).toBeInTheDocument();
    expect(screen.getAllByText("Zeta Supplies")).toHaveLength(2);
    const table = within(screen.getByRole("table"));
    expect(table.getByText("Matched")).toBeInTheDocument();
    expect(table.getByText("Exception")).toBeInTheDocument();
    expect(screen.getByText("$250.00")).toBeInTheDocument();
  });

  it("shows an empty state when nothing matches", async () => {
    mockGet({ "/supplier-invoices": page([]) });
    renderWithProviders(<InvoicesPage />, { permissions: ["invoice:read"] });

    expect(await screen.findByText("No invoices found")).toBeInTheDocument();
  });
});
