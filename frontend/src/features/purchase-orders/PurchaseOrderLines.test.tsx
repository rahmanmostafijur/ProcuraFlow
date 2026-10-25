import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { POItem, PurchaseOrder } from "@/api/types";
import { configureFormatting, resetFormatting } from "@/lib/formatting";

import { PurchaseOrderLines } from "./PurchaseOrderLines";

const line = (overrides: Partial<POItem> = {}): POItem => ({
  id: 1,
  product_id: 7,
  quantity: 3,
  unit_price: "19.99",
  received_quantity: 0,
  tax_rate_id: 1,
  tax_name: "Germany VAT 19%",
  tax_percent: "19.0000",
  tax_inclusive: false,
  reverse_charge: false,
  line_net: "59.97",
  line_tax: "11.39",
  line_total: "71.36",
  ...overrides,
});

const purchaseOrder = (overrides: Partial<PurchaseOrder> = {}): PurchaseOrder =>
  ({
    id: 1,
    po_number: "PO-2026-00001",
    currency_code: "EUR",
    items: [line()],
    notes: null,
    subtotal: "59.97",
    tax_total: "11.39",
    grand_total: "71.36",
    exchange_rate: null,
    base_subtotal: null,
    base_tax_total: null,
    base_grand_total: null,
    total: "71.36",
    ...overrides,
  }) as PurchaseOrder;

afterEach(() => resetFormatting());

describe("PurchaseOrderLines", () => {
  it("shows each line's tax and the totals in the order's currency", () => {
    render(<PurchaseOrderLines po={purchaseOrder()} />);

    const row = screen.getByRole("row", { name: /19\.99/ });
    expect(within(row).getByText("Germany VAT 19% 19%")).toBeInTheDocument();
    expect(within(row).getByText("€71.36")).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /^Subtotal/ })).toHaveTextContent("€59.97");
    expect(screen.getByRole("row", { name: /^Total \(EUR\)/ })).toHaveTextContent("€71.36");
  });

  it("adds up the tax per rate across lines without drift", () => {
    const items = [line({ id: 1, product_id: 1, line_tax: "0.10" }), line({ id: 2, product_id: 2, line_tax: "0.20" })];

    render(<PurchaseOrderLines po={purchaseOrder({ items })} />);

    expect(screen.getByRole("row", { name: /^Germany VAT 19%/ })).toHaveTextContent("€0.30");
  });

  it("shows a dash for a line without tax and no breakdown rows", () => {
    const items = [line({ tax_rate_id: null, tax_name: null, tax_percent: "0", line_tax: "0.00" })];

    render(<PurchaseOrderLines po={purchaseOrder({ items })} />);

    expect(screen.getAllByText("—")).not.toHaveLength(0);
    expect(screen.queryByRole("row", { name: /^Germany VAT/ })).not.toBeInTheDocument();
  });

  it("marks reverse-charge lines", () => {
    const items = [
      line({ tax_name: "EU reverse charge 0%", tax_percent: "0", reverse_charge: true, line_tax: "0.00" }),
    ];

    render(<PurchaseOrderLines po={purchaseOrder({ items })} />);

    expect(screen.getByText(/buyer accounts for tax/)).toBeInTheDocument();
  });

  it("shows the locked base-currency total once the order is approved", () => {
    configureFormatting({ currency: "USD" });
    const po = purchaseOrder({
      exchange_rate: "1.10000000",
      base_subtotal: "65.97",
      base_tax_total: "12.53",
      base_grand_total: "78.50",
    });

    render(<PurchaseOrderLines po={po} />);

    expect(screen.getByRole("row", { name: /approved rate of 1\.1/ })).toHaveTextContent("$78.50");
  });

  it("hides the base-currency total while the rate is not locked", () => {
    render(<PurchaseOrderLines po={purchaseOrder()} />);

    expect(screen.queryByText(/approved rate/)).not.toBeInTheDocument();
  });
});
