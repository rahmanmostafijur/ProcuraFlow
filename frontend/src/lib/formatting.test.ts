import { afterEach, describe, expect, it } from "vitest";

import { configureFormatting, formatCurrency, formatDate, formatDateTime, resetFormatting } from "./formatting";

afterEach(() => resetFormatting());

describe("formatDate", () => {
  it.each([
    ["MM/DD/YYYY", "03/15/2026"],
    ["DD/MM/YYYY", "15/03/2026"],
    ["DD.MM.YYYY", "15.03.2026"],
    ["YYYY-MM-DD", "2026-03-15"],
  ] as const)("renders a calendar date in the %s pattern", (dateFormat, expected) => {
    configureFormatting({ dateFormat });

    expect(formatDate("2026-03-15")).toBe(expected);
  });

  it("never shifts a calendar date by the time zone", () => {
    configureFormatting({ dateFormat: "YYYY-MM-DD", timeZone: "America/Los_Angeles" });

    expect(formatDate("2026-03-15")).toBe("2026-03-15");
  });

  it("converts a timestamp to the company's time zone before taking the day", () => {
    configureFormatting({ dateFormat: "YYYY-MM-DD", timeZone: "Asia/Tokyo" });

    expect(formatDate("2026-03-15T20:00:00Z")).toBe("2026-03-16");
  });

  it("returns a placeholder for empty or invalid values", () => {
    expect(formatDate(null)).toBe("—");
    expect(formatDate(undefined)).toBe("—");
    expect(formatDate("not a date")).toBe("—");
  });
});

describe("formatDateTime", () => {
  it("shows the date pattern and a 24-hour time in the company's zone", () => {
    configureFormatting({ dateFormat: "DD.MM.YYYY", timeZone: "Europe/Berlin" });

    expect(formatDateTime("2026-07-01T10:05:00Z")).toBe("01.07.2026 12:05");
  });
});

describe("formatCurrency", () => {
  it("uses the base currency by default", () => {
    configureFormatting({ currency: "EUR" });

    expect(formatCurrency("1234.5")).toBe("€1,234.50");
  });

  it("formats an explicit currency", () => {
    expect(formatCurrency(99, "GBP")).toBe("£99.00");
  });
});
