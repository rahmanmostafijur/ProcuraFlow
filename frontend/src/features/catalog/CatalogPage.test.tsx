import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import type { CatalogItem } from "@/api/types";
import { mockGet, renderWithProviders } from "@/test/render";

import { CatalogPage } from "./CatalogPage";

function item(overrides: Partial<CatalogItem>): CatalogItem {
  return {
    id: 1,
    product_id: 9,
    product_sku: "CAB-1",
    product_name: "Cable",
    supplier_id: 3,
    supplier_name: "Acme Supplies",
    contract_price: "4.5000",
    currency_code: "USD",
    lead_time_days: 7,
    valid_from: null,
    valid_until: null,
    is_active: true,
    is_current: true,
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

const list = [item({}), item({ id: 2, product_name: "Old plug", is_current: false, valid_until: "2025-12-31" })];
const page = (items: unknown[]) => ({ items, total: items.length, page: 1, page_size: 100, total_pages: 1 });

function serve() {
  return mockGet({
    "/catalog-items": list,
    "/products": page([{ id: 9, sku: "CAB-1", name: "Cable" }]),
    "/suppliers": page([{ id: 3, name: "Acme Supplies" }]),
    "/currencies": [{ code: "USD", name: "US Dollar", symbol: "$", minor_units: 2, is_active: true }],
  });
}

describe("CatalogPage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("marks current and not current prices", async () => {
    serve();
    renderWithProviders(<CatalogPage />);

    const current = (await screen.findByText("Cable")).closest("tr") as HTMLElement;
    expect(within(current).getByText("Current")).toBeInTheDocument();
    expect(within(current).getByText("$4.50")).toBeInTheDocument();
    const old = screen.getByText("Old plug").closest("tr") as HTMLElement;
    expect(within(old).getByText("Not current")).toBeInTheDocument();
  });

  it("hides creating and editing from people without catalog:manage", async () => {
    serve();
    renderWithProviders(<CatalogPage />);
    await screen.findByText("Cable");

    expect(screen.queryByRole("button", { name: /New contract price/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Edit/ })).not.toBeInTheDocument();
  });

  it("searches by the typed text", async () => {
    const get = serve();
    renderWithProviders(<CatalogPage />);
    await screen.findByText("Cable");

    fireEvent.change(screen.getByLabelText("Search the catalog"), { target: { value: "plug" } });

    await waitFor(() => expect(get).toHaveBeenCalledWith("/catalog-items", { params: { search: "plug" } }));
  });

  it("validates and creates a contract price", async () => {
    serve();
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: item({}) });
    renderWithProviders(<CatalogPage />, { permissions: ["catalog:manage"] });

    fireEvent.click(await screen.findByRole("button", { name: /New contract price/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Save" }));
    expect(await screen.findByText("Choose a product", { selector: "p" })).toBeInTheDocument();
    expect(screen.getByText("Choose a supplier", { selector: "p" })).toBeInTheDocument();
    expect(screen.getByText("A price with up to 4 decimals")).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();

    await screen.findAllByRole("option", { name: "CAB-1 — Cable" });
    fireEvent.change(screen.getByLabelText(/Product/), { target: { value: "9" } });
    fireEvent.change(screen.getByLabelText(/Supplier/), { target: { value: "3" } });
    fireEvent.change(screen.getByLabelText(/Contract price/), { target: { value: "4.25" } });
    fireEvent.change(screen.getByLabelText("Valid from"), { target: { value: "2026-06-01" } });
    fireEvent.change(screen.getByLabelText("Valid until"), { target: { value: "2026-01-01" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("The contract cannot end before it starts")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Valid until"), { target: { value: "2026-12-31" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/catalog-items", {
        product_id: 9,
        supplier_id: 3,
        currency_code: null,
        contract_price: "4.25",
        lead_time_days: 0,
        valid_from: "2026-06-01",
        valid_until: "2026-12-31",
      }),
    );
  });
});
