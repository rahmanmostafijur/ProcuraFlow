import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ConvertInput } from "@/api/purchaseRequests";
import { purchaseRequest, requestLine } from "@/test/fixtures";
import { mockGet, renderWithProviders } from "@/test/render";

import { ConvertRequestModal } from "./ConvertRequestModal";
import { buildConvertInput, initialAssignments, validateAssignments } from "./convertRequest";

const page = <T,>(items: T[]) => ({ items, total: items.length, page: 1, page_size: 100, total_pages: 1 });

function open(lines = [requestLine()]) {
  mockGet({
    "/suppliers": page([
      { id: 3, name: "Acme Supplies" },
      { id: 4, name: "Bolt Co" },
    ]),
    "/products": page([{ id: 9, sku: "LAP-1", name: "Laptop" }]),
  });
  const onSubmit = vi.fn<(input: ConvertInput) => void>();
  renderWithProviders(
    <ConvertRequestModal
      isOpen
      request={purchaseRequest({ status: "approved", lines })}
      isSubmitting={false}
      onClose={vi.fn()}
      onSubmit={onSubmit}
    />,
  );
  return onSubmit;
}

describe("ConvertRequestModal", () => {
  afterEach(() => vi.restoreAllMocks());

  it("needs a product for a free-text line", async () => {
    const onSubmit = open();
    await screen.findByRole("option", { name: "Acme Supplies" });

    fireEvent.change(screen.getByLabelText("Supplier for line 1"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Create purchase orders" }));
    expect(await screen.findByText("Choose the product to order", { selector: "p" })).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Product for line 1"), { target: { value: "9" } });
    fireEvent.click(screen.getByRole("button", { name: "Create purchase orders" }));

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith({
        orders: [{ supplier_id: 3, expected_delivery_date: null, lines: [{ line_id: 11, product_id: 9 }] }],
      }),
    );
  });

  it("does not ask for a product on a line that already has one, and groups by supplier", async () => {
    const onSubmit = open([
      requestLine({ id: 11, product_id: 9, supplier_id: 3 }),
      requestLine({ id: 12, description: "Mouse", product_id: 10, supplier_id: 3 }),
      requestLine({ id: 13, description: "Cable", product_id: 11, supplier_id: 4 }),
    ]);
    await screen.findByLabelText("Supplier for line 3");

    expect(screen.queryByLabelText("Product for line 1")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Create purchase orders" }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit.mock.calls[0][0].orders.map((order) => order.supplier_id)).toEqual([3, 4]);
    expect(onSubmit.mock.calls[0][0].orders[0].lines).toHaveLength(2);
  });

  it("disables a line that is already ordered", async () => {
    open([requestLine({ id: 11, converted_po_id: 70 }), requestLine({ id: 12, description: "Mouse" })]);

    const ordered = await screen.findByLabelText("Include line 1");
    expect(ordered).toBeDisabled();
    expect(ordered).not.toBeChecked();
    expect(screen.getByText("(already ordered)")).toBeInTheDocument();
    expect(screen.getByLabelText("Include line 2")).toBeEnabled();
  });

  it("refuses to submit when every line is left out", async () => {
    const onSubmit = open();
    fireEvent.click(await screen.findByLabelText("Include line 1"));

    fireEvent.click(screen.getByRole("button", { name: "Create purchase orders" }));

    expect(await screen.findByText("Include at least one line")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});

describe("convertRequest helpers", () => {
  it("skips ordered lines when validating and building", () => {
    const lines = [requestLine({ id: 1, converted_po_id: 5 }), requestLine({ id: 2, product_id: 9, supplier_id: 3 })];
    const assignments = initialAssignments(lines);

    expect(validateAssignments(lines, assignments)).toEqual({});
    expect(buildConvertInput(lines, assignments, "2026-12-01").orders).toEqual([
      { supplier_id: 3, expected_delivery_date: "2026-12-01", lines: [{ line_id: 2, product_id: 9 }] },
    ]);
  });
});
