import { describe, expect, it } from "vitest";

import { toProductPayload } from "./productPayload";

const values = {
  sku: "OFF-1001",
  name: "Copy Paper",
  category_id: "3",
  unit: "ream",
  cost: 4.5,
  minimum_stock: 10,
  supplier_id: "",
  is_active: "false" as const,
};

describe("toProductPayload", () => {
  it("sends only the fields a new product accepts", () => {
    expect(toProductPayload(values, false)).toEqual({
      sku: "OFF-1001",
      name: "Copy Paper",
      category_id: 3,
      unit: "ream",
      cost: "4.50",
      minimum_stock: 10,
      supplier_id: null,
    });
  });

  it("never sends stock, which is recorded through the inventory ledger", () => {
    expect(toProductPayload(values, false)).not.toHaveProperty("current_stock");
    expect(toProductPayload(values, true)).not.toHaveProperty("current_stock");
  });

  it("includes the active flag when editing", () => {
    expect(toProductPayload(values, true)).toMatchObject({ is_active: false });
  });
});
