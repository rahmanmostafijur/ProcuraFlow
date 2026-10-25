import { describe, expect, it } from "vitest";

import { documentLink } from "./documentLinks";

describe("documentLink", () => {
  it("opens a request or an order by its own id", () => {
    expect(documentLink("purchase_request", 5)).toBe("/requests/5");
    expect(documentLink("purchase_order", 7, 7)).toBe("/purchase-orders/7");
  });

  it("opens the order an amendment changes, not the amendment's own id", () => {
    expect(documentLink("purchase_order_amendment", 31, 7)).toBe("/purchase-orders/7");
  });

  it("falls back to the order list when the order is not known, and has no page for invoice exceptions", () => {
    expect(documentLink("purchase_order_amendment", 31)).toBe("/purchase-orders");
    expect(documentLink("invoice_exception", 1)).toBeNull();
  });
});
