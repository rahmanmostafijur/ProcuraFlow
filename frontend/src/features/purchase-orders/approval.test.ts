import { describe, expect, it } from "vitest";

import { canApprovePurchaseOrder, needsAnotherApprover } from "./approval";

const creator = { id: 1 };
const otherApprover = { id: 2 };
const submittedPo = { status: "submitted" as const, creator };

const grants = (...codes: string[]) => (code: string) => codes.includes(code);

describe("canApprovePurchaseOrder", () => {
  it("hides approval from the user who created the purchase order", () => {
    expect(canApprovePurchaseOrder(submittedPo, creator, grants("po:approve"))).toBe(false);
  });

  it("allows another user with the approve permission", () => {
    expect(canApprovePurchaseOrder(submittedPo, otherApprover, grants("po:approve"))).toBe(true);
  });

  it("hides approval from a user without the approve permission", () => {
    expect(canApprovePurchaseOrder(submittedPo, otherApprover, grants("po:create"))).toBe(false);
  });

  it("hides approval when the purchase order is not submitted", () => {
    const draftPo = { ...submittedPo, status: "draft" as const };
    const approvedPo = { ...submittedPo, status: "approved" as const };

    expect(canApprovePurchaseOrder(draftPo, otherApprover, grants("po:approve"))).toBe(false);
    expect(canApprovePurchaseOrder(approvedPo, otherApprover, grants("po:approve"))).toBe(false);
  });

  it("hides approval when no user is signed in", () => {
    expect(canApprovePurchaseOrder(submittedPo, null, grants("po:approve"))).toBe(false);
  });
});

describe("needsAnotherApprover", () => {
  it("is true for an approver looking at a submitted purchase order they created", () => {
    expect(needsAnotherApprover(submittedPo, creator, grants("po:approve"))).toBe(true);
  });

  it("is false for a different approver", () => {
    expect(needsAnotherApprover(submittedPo, otherApprover, grants("po:approve"))).toBe(false);
  });

  it("is false for a creator who could not approve anyway", () => {
    expect(needsAnotherApprover(submittedPo, creator, grants("po:create"))).toBe(false);
  });

  it("is false once the purchase order has left the submitted status", () => {
    const approvedPo = { ...submittedPo, status: "approved" as const };

    expect(needsAnotherApprover(approvedPo, creator, grants("po:approve"))).toBe(false);
  });
});
