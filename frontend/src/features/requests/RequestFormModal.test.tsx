import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { PurchaseRequestInput } from "@/api/purchaseRequests";
import type { CatalogItem } from "@/api/types";
import { mockGet, renderWithProviders } from "@/test/render";

import { RequestFormModal } from "./RequestFormModal";

const catalogItem: CatalogItem = {
  id: 21,
  product_id: 9,
  product_sku: "LAP-1",
  product_name: "Laptop 14in",
  supplier_id: 3,
  supplier_name: "Acme Supplies",
  contract_price: "2300.0000",
  currency_code: "USD",
  lead_time_days: 5,
  valid_from: null,
  valid_until: null,
  is_active: true,
  is_current: true,
  created_at: "2026-01-01T00:00:00Z",
};

function serve() {
  mockGet({
    "/cost-centres": [{ id: 4, code: "IT", name: "Information Technology", manager_id: null, is_active: true }],
    "/currencies": [{ code: "USD", name: "US Dollar", symbol: "$", minor_units: 2, is_active: true }],
    "/catalog-items": [catalogItem],
  });
}

function open(onSubmit = vi.fn<(input: PurchaseRequestInput) => Promise<void>>().mockResolvedValue(undefined)) {
  serve();
  renderWithProviders(<RequestFormModal isOpen isSubmitting={false} onClose={vi.fn()} onSubmit={onSubmit} />);
  return onSubmit;
}

describe("RequestFormModal", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows what is missing and sends nothing", async () => {
    const onSubmit = open();

    fireEvent.click(await screen.findByRole("button", { name: "Save as draft" }));

    expect(await screen.findByText("Give the request a title")).toBeInTheDocument();
    expect(screen.getByText("Describe what is needed")).toBeInTheDocument();
    expect(screen.getByText("A price with up to 4 decimals")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits the typed request with ids as numbers and empty choices as null", async () => {
    const onSubmit = open();
    await screen.findByRole("option", { name: "IT — Information Technology" });

    fireEvent.change(screen.getByLabelText(/Title/), { target: { value: "Desk chairs" } });
    fireEvent.change(screen.getByLabelText("Cost centre"), { target: { value: "4" } });
    fireEvent.change(screen.getByLabelText("Needed by"), { target: { value: "2026-12-01" } });
    fireEvent.change(screen.getByLabelText("Description for line 1"), { target: { value: "Chair" } });
    fireEvent.change(screen.getByLabelText("Quantity for line 1"), { target: { value: "6" } });
    fireEvent.change(screen.getByLabelText("Estimated unit price for line 1"), { target: { value: "129.5" } });
    fireEvent.click(screen.getByRole("button", { name: "Save as draft" }));

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith({
        title: "Desk chairs",
        notes: null,
        cost_centre_id: 4,
        currency_code: null,
        needed_by: "2026-12-01",
        lines: [
          {
            description: "Chair",
            quantity: 6,
            unit: "unit",
            estimated_unit_price: "129.5",
            catalog_item_id: null,
            product_id: null,
            supplier_id: null,
          },
        ],
      }),
    );
  });

  it("fills price, product and supplier from a catalog pick", async () => {
    const onSubmit = open();
    await screen.findByRole("option", { name: /Laptop 14in/ });

    fireEvent.change(screen.getByLabelText(/Title/), { target: { value: "Laptops" } });
    fireEvent.change(screen.getByLabelText("Catalog item for line 1"), { target: { value: "21" } });

    expect(screen.getByLabelText("Description for line 1")).toHaveValue("Laptop 14in");
    expect(screen.getByLabelText("Estimated unit price for line 1")).toHaveValue("2300.0000");
    fireEvent.click(screen.getByRole("button", { name: "Save as draft" }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit.mock.calls[0][0].lines[0]).toMatchObject({
      catalog_item_id: 21,
      product_id: 9,
      supplier_id: 3,
      estimated_unit_price: "2300.0000",
    });
  });

  it("gives each added line its own labels and keeps the last line", async () => {
    open();
    await screen.findByLabelText("Description for line 1");
    expect(screen.getByRole("button", { name: "Remove line 1" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Add line" }));

    expect(screen.getByLabelText("Description for line 2")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove line 1" })).toBeEnabled();
  });
});
