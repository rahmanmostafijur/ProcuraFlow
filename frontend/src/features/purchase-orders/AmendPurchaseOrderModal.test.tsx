import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { purchaseOrder } from "@/test/fixtures";
import { mockGet, renderWithProviders } from "@/test/render";

import { AmendPurchaseOrderModal } from "./AmendPurchaseOrderModal";

function open() {
  mockGet({
    "/products": {
      items: [
        { id: 9, sku: "CAB-1", name: "Cable" },
        { id: 10, sku: "PLG-2", name: "Plug" },
      ],
      total: 2,
      page: 1,
      page_size: 100,
      total_pages: 1,
    },
    "/tax-rates": [],
  });
  const onSubmit = vi.fn().mockResolvedValue(undefined);
  renderWithProviders(
    <AmendPurchaseOrderModal
      isOpen
      po={purchaseOrder({ status: "ordered" })}
      isSubmitting={false}
      onClose={vi.fn()}
      onSubmit={onSubmit}
    />,
  );
  return onSubmit;
}

describe("AmendPurchaseOrderModal", () => {
  afterEach(() => vi.restoreAllMocks());

  it("explains that a bigger total waits for approval", async () => {
    open();

    expect(await screen.findByText(/raises the total waits for approval/)).toBeInTheDocument();
  });

  it("starts from the order's current lines", async () => {
    open();

    expect(await screen.findByLabelText("Quantity for line 1")).toHaveValue(10);
    expect(screen.getByLabelText("Unit price for line 1")).toHaveValue(5);
  });

  it("requires a reason", async () => {
    const onSubmit = open();
    await screen.findByRole("option", { name: "CAB-1 — Cable" });

    fireEvent.click(screen.getByRole("button", { name: "Submit change" }));

    expect(await screen.findByText("Say why the order is changing")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("sends the reason with the full list of lines", async () => {
    const onSubmit = open();
    await screen.findByRole("option", { name: "CAB-1 — Cable" });

    fireEvent.change(screen.getByLabelText(/Reason for the change/), {
      target: { value: "Supplier raised the price" },
    });
    fireEvent.change(screen.getByLabelText("Quantity for line 1"), { target: { value: "12" } });
    fireEvent.change(screen.getByLabelText("Unit price for line 1"), { target: { value: "5.25" } });
    fireEvent.change(screen.getByLabelText("Expected delivery"), { target: { value: "2026-12-15" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit change" }));

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith({
        reason: "Supplier raised the price",
        expected_delivery_date: "2026-12-15",
        notes: null,
        items: [{ product_id: 9, quantity: 12, unit_price: "5.2500", tax_rate_id: null }],
      }),
    );
  });

  it("rejects the same product on two lines and keeps the last line", async () => {
    const onSubmit = open();
    await screen.findByRole("option", { name: "CAB-1 — Cable" });
    expect(screen.getByRole("button", { name: "Remove line 1" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Add item" }));
    fireEvent.change(screen.getByLabelText("Product for line 2"), { target: { value: "9" } });
    fireEvent.change(screen.getByLabelText(/Reason for the change/), { target: { value: "More" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit change" }));

    expect(await screen.findByText(/Each product can appear only once/)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
