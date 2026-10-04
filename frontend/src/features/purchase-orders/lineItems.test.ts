import { describe, expect, it } from "vitest";

import { duplicateProductMessage, productIdsChosenOnOtherLines, purchaseOrderFormSchema } from "./lineItems";

const line = (product_id: string, quantity = 1) => ({ product_id, quantity, unit_price: 5 });

const formValues = (...items: ReturnType<typeof line>[]) => ({ supplier_id: "1", items });

describe("productIdsChosenOnOtherLines", () => {
  it("returns the products picked on every other line", () => {
    const items = [line("3"), line("7"), line("9")];

    expect(productIdsChosenOnOtherLines(items, 1)).toEqual(new Set(["3", "9"]));
  });

  it("ignores lines where no product has been picked yet", () => {
    const items = [line(""), line("7")];

    expect(productIdsChosenOnOtherLines(items, 1)).toEqual(new Set());
  });

  it("does not block a line from keeping its own product", () => {
    expect(productIdsChosenOnOtherLines([line("4")], 0).has("4")).toBe(false);
  });
});

describe("purchaseOrderFormSchema", () => {
  it("accepts one line per product", () => {
    expect(purchaseOrderFormSchema.safeParse(formValues(line("3"), line("7"))).success).toBe(true);
  });

  it("rejects the same product on two lines and points at the repeated line", () => {
    const result = purchaseOrderFormSchema.safeParse(formValues(line("3"), line("7"), line("3", 2)));

    expect(result.success).toBe(false);
    expect(result.error?.issues).toEqual([
      expect.objectContaining({ path: ["items", 2, "product_id"], message: duplicateProductMessage("3") }),
    ]);
  });

  it("uses the same wording as the API", () => {
    expect(duplicateProductMessage("12")).toBe(
      "Each product can appear only once per purchase order (product 12 is repeated). Combine the quantities into one line."
    );
  });
});
