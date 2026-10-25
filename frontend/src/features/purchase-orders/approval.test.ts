import { describe, expect, it } from "vitest";

import type { QueueItem } from "@/api/types";

import { canDecidePurchaseOrder, isInQueue, needsAnotherApprover } from "./approval";

const creator = { id: 1 };
const otherApprover = { id: 2 };
const submittedPo = { id: 7, status: "submitted" as const, creator };

const queueItem = (overrides: Partial<QueueItem> = {}): QueueItem => ({
  document_type: "purchase_order",
  document_id: 7,
  po_id: 7,
  label: "PO-0007",
  title: "Order",
  amount_base: "100.00",
  requester: { id: 1, full_name: "Creator" },
  submitted_at: null,
  step_order: 1,
  steps_total: 1,
  rule_name: null,
  on_behalf_of: null,
  ...overrides,
});

const grants =
  (...codes: string[]) =>
  (code: string) =>
    codes.includes(code);

describe("isInQueue", () => {
  it("matches the document type and id together", () => {
    const queue = [queueItem()];

    expect(isInQueue(queue, "purchase_order", 7)).toBe(true);
    expect(isInQueue(queue, "purchase_request", 7)).toBe(false);
    expect(isInQueue(queue, "purchase_order", 8)).toBe(false);
  });

  it("is false while the queue has not loaded", () => {
    expect(isInQueue(undefined, "purchase_order", 7)).toBe(false);
  });
});

describe("canDecidePurchaseOrder", () => {
  it("allows a user whose queue holds the submitted order", () => {
    expect(canDecidePurchaseOrder(submittedPo, [queueItem()])).toBe(true);
  });

  it("hides the decision from a user who has the permission but not the order in the queue", () => {
    expect(canDecidePurchaseOrder(submittedPo, [])).toBe(false);
  });

  it("hides the decision when the order is not submitted, even if a stale queue lists it", () => {
    expect(canDecidePurchaseOrder({ ...submittedPo, status: "draft" }, [queueItem()])).toBe(false);
    expect(canDecidePurchaseOrder({ ...submittedPo, status: "approved" }, [queueItem()])).toBe(false);
  });

  it("hides the decision before the queue has loaded", () => {
    expect(canDecidePurchaseOrder(submittedPo, undefined)).toBe(false);
  });
});

describe("needsAnotherApprover", () => {
  it("is true for an approver looking at a submitted order they created and cannot decide", () => {
    expect(needsAnotherApprover(submittedPo, creator, grants("po:approve"), [])).toBe(true);
  });

  it("is false for a different approver", () => {
    expect(needsAnotherApprover(submittedPo, otherApprover, grants("po:approve"), [])).toBe(false);
  });

  it("is false for a creator who could not approve anyway", () => {
    expect(needsAnotherApprover(submittedPo, creator, grants("po:create"), [])).toBe(false);
  });

  it("is false when the creator can in fact decide it", () => {
    expect(needsAnotherApprover(submittedPo, creator, grants("po:approve"), [queueItem()])).toBe(false);
  });

  it("is false once the order has left the submitted status", () => {
    expect(needsAnotherApprover({ ...submittedPo, status: "approved" }, creator, grants("po:approve"), [])).toBe(false);
  });
});
