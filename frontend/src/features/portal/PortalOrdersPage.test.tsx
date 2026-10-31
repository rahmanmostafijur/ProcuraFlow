import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import type { PortalOrder } from "@/api/portal";
import { mockGet, renderWithProviders } from "@/test/render";

import { PortalOrdersPage } from "./PortalOrdersPage";

const order: PortalOrder = {
  id: 12,
  po_number: "PO-0012",
  status: "ordered",
  currency_code: "USD",
  subtotal: "100.00",
  tax_total: "0.00",
  grand_total: "100.00",
  expected_delivery_date: null,
  version: 1,
  created_at: "2026-10-30T09:00:00Z",
  acknowledged_at: null,
  items: [
    {
      product_id: 1,
      product_name: "Widget",
      sku: "W-1",
      quantity: 10,
      received_quantity: 0,
      unit_price: "10.0000",
      tax_name: null,
      tax_percent: "0",
      line_total: "100.00",
    },
  ],
};

describe("PortalOrdersPage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("acknowledges an order from its detail", async () => {
    mockGet({
      "/portal/orders": { items: [order], total: 1, page: 1, page_size: 10, total_pages: 1 },
      "/portal/orders/12": order,
    });
    const post = vi
      .spyOn(apiClient, "post")
      .mockResolvedValue({ data: { ...order, acknowledged_at: "2026-11-01T08:00:00Z" } });
    renderWithProviders(<PortalOrdersPage />);

    fireEvent.click(await screen.findByText("PO-0012"));
    expect(await screen.findByText("Widget")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Acknowledge order" }));

    await waitFor(() => expect(post).toHaveBeenCalledWith("/portal/orders/12/acknowledge"));
  });

  it("offers no acknowledge button once the order was acknowledged", async () => {
    const done = { ...order, acknowledged_at: "2026-11-01T08:00:00Z" };
    mockGet({
      "/portal/orders": { items: [done], total: 1, page: 1, page_size: 10, total_pages: 1 },
      "/portal/orders/12": done,
    });
    renderWithProviders(<PortalOrdersPage />);

    fireEvent.click(await screen.findByText("PO-0012"));

    expect(await screen.findByText(/Acknowledged on/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Acknowledge order" })).not.toBeInTheDocument();
  });
});
