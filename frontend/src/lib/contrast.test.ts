import { describe, expect, it } from "vitest";

import { contrastRatio, readableTextOn, relativeLuminance } from "./contrast";

describe("relativeLuminance", () => {
  it("is 0 for black and 1 for white", () => {
    expect(relativeLuminance("#000000")).toBe(0);
    expect(relativeLuminance("#ffffff")).toBeCloseTo(1, 5);
  });

  it("returns null for anything that is not a six-digit hex colour", () => {
    expect(relativeLuminance("teal")).toBeNull();
    expect(relativeLuminance("#fff")).toBeNull();
    expect(relativeLuminance("")).toBeNull();
  });
});

describe("contrastRatio", () => {
  it("is 21 between black and white whichever way round", () => {
    expect(contrastRatio(1, 0)).toBeCloseTo(21, 5);
    expect(contrastRatio(0, 1)).toBeCloseTo(21, 5);
  });
});

describe("readableTextOn", () => {
  it("uses white on dark colours and dark text on light ones", () => {
    expect(readableTextOn("#0F766E")).toBe("#FFFFFF");
    expect(readableTextOn("#1E3A8A")).toBe("#FFFFFF");
    expect(readableTextOn("#FDE68A")).toBe("#0B1220");
    expect(readableTextOn("#34D399")).toBe("#0B1220");
  });

  it("falls back to white for a colour it cannot read", () => {
    expect(readableTextOn("not-a-colour")).toBe("#FFFFFF");
  });
});
