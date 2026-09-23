import { describe, expect, it } from "vitest";

import { cn, formatCurrency, formatDate } from "./utils";

describe("formatCurrency", () => {
  it("formats a numeric string as USD currency", () => {
    expect(formatCurrency("1234.5")).toBe("$1,234.50");
  });

  it("formats a plain number as USD currency", () => {
    expect(formatCurrency(99)).toBe("$99.00");
  });
});

describe("formatDate", () => {
  it("returns an em dash placeholder for null or undefined", () => {
    expect(formatDate(null)).toBe("—");
    expect(formatDate(undefined)).toBe("—");
  });

  it("formats an ISO date string", () => {
    expect(formatDate("2026-03-15")).toBe("Mar 15, 2026");
  });
});

describe("cn", () => {
  it("merges class names and drops falsy values", () => {
    expect(cn("a", false, "b", undefined, "c")).toBe("a b c");
  });
});
