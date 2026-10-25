import { describe, expect, it } from "vitest";

import { currencyDecimals, sumAmounts } from "./money";

describe("sumAmounts", () => {
  it("adds without floating-point drift", () => {
    expect(sumAmounts(["0.10", "0.20"], 2)).toBe("0.30");
    expect(sumAmounts(["19.99", "0.01", "5.00"], 2)).toBe("25.00");
  });

  it("returns zero for an empty list", () => {
    expect(sumAmounts([], 2)).toBe("0.00");
  });

  it("respects the currency's decimals", () => {
    expect(sumAmounts(["1000", "1"], 0)).toBe("1001");
    expect(sumAmounts(["1.234", "0.001"], 3)).toBe("1.235");
  });
});

describe("currencyDecimals", () => {
  it.each([
    ["USD", 2],
    ["JPY", 0],
    ["BHD", 3],
  ])("knows %s has %i decimals", (currency, expected) => {
    expect(currencyDecimals(currency)).toBe(expected);
  });

  it("falls back to two decimals for an unknown code", () => {
    expect(currencyDecimals("not a code")).toBe(2);
  });
});
