/**
 * Every number, money amount and date shown to a person is produced here, with Intl, from the company settings.
 * No screen assembles a currency or date string by hand.
 */
export type DateFormat = "YYYY-MM-DD" | "MM/DD/YYYY" | "DD/MM/YYYY" | "DD.MM.YYYY";

export interface FormattingConfig {
  dateFormat: DateFormat;
  timeZone: string;
  currency: string;
  /** BCP 47 locale for digits and separators; null means derive it (country, then the browser). */
  locale: string | null;
}

const DEFAULT_CONFIG: FormattingConfig = {
  dateFormat: "MM/DD/YYYY",
  timeZone: "UTC",
  currency: "USD",
  locale: null,
};
const PLACEHOLDER = "—";
const FALLBACK_LOCALE = "en-US";
const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/;
const DECIMAL_STRING = /^[+-]?\d+(\.\d+)?$/;

// Module-level so the many plain formatting calls across pages need no hook or prop. The company settings
// provider sets it before rendering the signed-in app, and re-keys the tree when it changes.
let config: FormattingConfig = DEFAULT_CONFIG;

export function configureFormatting(next: Partial<FormattingConfig>): void {
  config = { ...config, ...next };
}

export function resetFormatting(): void {
  config = DEFAULT_CONFIG;
}

export function getFormattingConfig(): FormattingConfig {
  return config;
}

/**
 * The company stores a country, not a locale, so combine the browser language with that country
 * (de + CH gives de-CH). An unusable combination falls back to the browser language, then en-US.
 */
export function deriveLocale(countryCode: string | null | undefined): string {
  const browser = typeof navigator === "undefined" ? FALLBACK_LOCALE : navigator.language || FALLBACK_LOCALE;
  if (!countryCode) return browser;
  try {
    return new Intl.Locale(browser.split("-")[0], { region: countryCode.toUpperCase() }).toString();
  } catch {
    return browser;
  }
}

function activeLocale(locale?: string): string {
  const requested = locale ?? config.locale ?? deriveLocale(null);
  try {
    return Intl.NumberFormat.supportedLocalesOf(requested)[0] ?? FALLBACK_LOCALE;
  } catch {
    return FALLBACK_LOCALE;
  }
}

function isBlank(value: unknown): value is null | undefined | "" {
  return value === null || value === undefined || value === "";
}

/**
 * Amounts arrive as decimal strings. Intl.NumberFormat formats a numeric string exactly (no float round trip),
 * so "12345678901234567.89" keeps every digit. The cast is only for lib typings that expect a number.
 */
function toFormattable(value: string | number): number | null {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  const trimmed = value.trim();
  if (DECIMAL_STRING.test(trimmed)) return trimmed as unknown as number;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatWith(
  value: string | number | null | undefined,
  options: Intl.NumberFormatOptions,
  locale?: string,
): string {
  if (isBlank(value)) return PLACEHOLDER;
  const amount = toFormattable(value);
  if (amount === null) return PLACEHOLDER;
  try {
    return new Intl.NumberFormat(activeLocale(locale), options).format(amount);
  } catch {
    return PLACEHOLDER;
  }
}

/** Minor units come from the runtime's currency data: 0 for JPY, 2 for EUR, 3 for BHD. */
export function formatMoney(
  amount: string | number | null | undefined,
  currency: string = config.currency,
  locale?: string,
): string {
  return formatWith(amount, { style: "currency", currency }, locale);
}

/** 1.2M style for dashboards; the full figure belongs in a tooltip. */
export function formatCompactMoney(
  amount: string | number | null | undefined,
  currency: string = config.currency,
  locale?: string,
): string {
  return formatWith(amount, { style: "currency", currency, notation: "compact", maximumFractionDigits: 1 }, locale);
}

export function formatNumber(
  value: string | number | null | undefined,
  options: Intl.NumberFormatOptions = {},
  locale?: string,
): string {
  return formatWith(value, options, locale);
}

/** `percent` is already in percent points (92.5 means 92.5%), as the API sends it. */
export function formatPercent(
  percent: string | number | null | undefined,
  fractionDigits = 1,
  locale?: string,
): string {
  return formatWith(
    percent,
    { style: "unit", unit: "percent", minimumFractionDigits: fractionDigits, maximumFractionDigits: fractionDigits },
    locale,
  );
}

function assemble(year: string, month: string, day: string): string {
  switch (config.dateFormat) {
    case "YYYY-MM-DD":
      return `${year}-${month}-${day}`;
    case "DD/MM/YYYY":
      return `${day}/${month}/${year}`;
    case "DD.MM.YYYY":
      return `${day}.${month}.${year}`;
    case "MM/DD/YYYY":
      return `${month}/${day}/${year}`;
  }
}

function zonedParts(date: Date): Record<"year" | "month" | "day" | "hour" | "minute", string> {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: config.timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const pick = (type: Intl.DateTimeFormatPartTypes) => parts.find((part) => part.type === type)?.value ?? "";
  return { year: pick("year"), month: pick("month"), day: pick("day"), hour: pick("hour"), minute: pick("minute") };
}

/**
 * The date pattern is the company's own setting (date_format), so the digits are arranged from Intl's zoned parts
 * rather than the locale. A calendar date ("2026-03-15") is shown as is; a timestamp is first converted to the
 * company's time zone.
 */
export function formatDate(value: string | null | undefined): string {
  if (!value) return PLACEHOLDER;
  const dateOnly = DATE_ONLY.exec(value);
  if (dateOnly) return assemble(dateOnly[1], dateOnly[2], dateOnly[3]);
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return PLACEHOLDER;
  const { year, month, day } = zonedParts(date);
  return assemble(year, month, day);
}

const MONTH_KEY = /^(\d{4})-(\d{2})$/;

/** "2026-05" as "May 2026" in the company locale (a calendar month, so no time zone shift applies). */
export function formatMonth(value: string | number | null | undefined): string {
  const match = typeof value === "string" ? MONTH_KEY.exec(value) : null;
  if (!match) return typeof value === "string" && value !== "" ? value : PLACEHOLDER;
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, 1));
  try {
    return new Intl.DateTimeFormat(activeLocale(), { month: "short", year: "numeric", timeZone: "UTC" }).format(date);
  } catch {
    return match[0];
  }
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return PLACEHOLDER;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return PLACEHOLDER;
  const { year, month, day, hour, minute } = zonedParts(date);
  return `${assemble(year, month, day)} ${hour}:${minute}`;
}

const RELATIVE_UNITS: ReadonlyArray<[Intl.RelativeTimeFormatUnit, number]> = [
  ["year", 31_536_000],
  ["month", 2_592_000],
  ["week", 604_800],
  ["day", 86_400],
  ["hour", 3_600],
  ["minute", 60],
];

/** "3 hours ago", "in 2 days", "yesterday", in the company locale. `now` is injectable for tests. */
export function formatRelative(value: string | null | undefined, now: Date = new Date(), locale?: string): string {
  if (!value) return PLACEHOLDER;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return PLACEHOLDER;
  const seconds = Math.round((date.getTime() - now.getTime()) / 1000);
  const [unit, size] = RELATIVE_UNITS.find(([, length]) => Math.abs(seconds) >= length) ?? ["second", 1];
  const formatter = new Intl.RelativeTimeFormat(activeLocale(locale), { numeric: "auto" });
  return formatter.format(Math.trunc(seconds / size), unit);
}
