import { afterEach, describe, expect, it } from "vitest";

import {
  configureFormatting,
  deriveLocale,
  formatCompactMoney,
  formatMoney,
  formatNumber,
  formatPercent,
  formatRelative,
  resetFormatting,
} from "./format";

// Intl puts a no-break space between amount and symbol in several locales; the \s class matches it.
const plain = (text: string) => text.replace(/\s/g, " ");

afterEach(() => resetFormatting());

describe("formatMoney", () => {
  it.each([
    ["1234.5", "USD", "en-US", "$1,234.50"],
    ["1234.5", "EUR", "de-DE", "1.234,50 €"],
    ["1234.5", "GBP", "en-GB", "£1,234.50"],
    ["1234", "JPY", "en-US", "¥1,234"],
    ["1234.567", "BHD", "en-US", "BHD 1,234.567"],
  ])("formats %s %s in %s", (amount, currency, locale, expected) => {
    expect(plain(formatMoney(amount, currency, locale))).toBe(expected);
  });

  it("uses the minor units of the currency, not two decimals", () => {
    expect(plain(formatMoney("5", "JPY", "en-US"))).toBe("¥5");
    expect(plain(formatMoney("5", "BHD", "en-US"))).toBe("BHD 5.000");
  });

  it("shows negatives with a sign", () => {
    expect(plain(formatMoney("-1234.5", "USD", "en-US"))).toBe("-$1,234.50");
    expect(plain(formatMoney(-12, "EUR", "de-DE"))).toBe("-12,00 €");
  });

  it("keeps every digit of a large decimal string", () => {
    expect(formatMoney("12345678901234567.89", "USD", "en-US")).toBe("$12,345,678,901,234,567.89");
  });

  it("does not drift on values that floats misround", () => {
    expect(formatMoney("0.30", "USD", "en-US")).toBe("$0.30");
    expect(formatMoney("1.005", "USD", "en-US")).toBe("$1.01");
  });

  it("returns a placeholder for missing or unreadable values", () => {
    expect(formatMoney(null)).toBe("—");
    expect(formatMoney(undefined)).toBe("—");
    expect(formatMoney("")).toBe("—");
    expect(formatMoney("abc")).toBe("—");
  });

  it("defaults to the company currency and falls back to a supported locale", () => {
    configureFormatting({ currency: "EUR", locale: "de-DE" });
    expect(plain(formatMoney("10"))).toBe("10,00 €");
    expect(formatMoney("10", "USD", "not a locale!!")).toBe("$10.00");
  });
});

describe("formatCompactMoney", () => {
  it("abbreviates large amounts", () => {
    expect(formatCompactMoney("1250000", "USD", "en-US")).toBe("$1.3M");
    expect(formatCompactMoney(null)).toBe("—");
  });
});

describe("formatNumber and formatPercent", () => {
  it("groups digits by locale", () => {
    expect(formatNumber("1234567.891", { maximumFractionDigits: 2 }, "en-US")).toBe("1,234,567.89");
    expect(formatNumber(1234567.891, { maximumFractionDigits: 2 }, "de-DE")).toBe("1.234.567,89");
  });

  it("formats percent points without dividing", () => {
    expect(formatPercent("92.5", 1, "en-US")).toBe("92.5%");
    expect(plain(formatPercent("92.5", 1, "de-DE"))).toBe("92,5 %");
    expect(formatPercent(null)).toBe("—");
  });
});

describe("formatRelative", () => {
  const now = new Date("2026-03-15T12:00:00Z");

  it.each([
    ["2026-03-15T09:00:00Z", "3 hours ago"],
    ["2026-03-17T12:00:00Z", "in 2 days"],
    ["2026-03-14T12:00:00Z", "yesterday"],
  ])("describes %s", (value, expected) => {
    expect(formatRelative(value, now, "en-US")).toBe(expected);
  });

  it("returns a placeholder for invalid input", () => {
    expect(formatRelative("nope", now)).toBe("—");
    expect(formatRelative(null, now)).toBe("—");
  });
});

describe("deriveLocale", () => {
  it("combines the browser language with the company country", () => {
    expect(deriveLocale("CH")).toMatch(/^en-CH$/);
  });

  it("falls back to the browser language for a missing or invalid country", () => {
    expect(deriveLocale(null)).toBe(navigator.language);
    expect(deriveLocale("not-a-country!")).toBe(navigator.language);
  });
});
