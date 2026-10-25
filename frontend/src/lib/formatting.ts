export type DateFormat = "YYYY-MM-DD" | "MM/DD/YYYY" | "DD/MM/YYYY" | "DD.MM.YYYY";

export interface FormattingConfig {
  dateFormat: DateFormat;
  timeZone: string;
  currency: string;
}

const DEFAULT_CONFIG: FormattingConfig = { dateFormat: "MM/DD/YYYY", timeZone: "UTC", currency: "USD" };
const PLACEHOLDER = "—";
const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/;

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

/** A calendar date ("2026-03-15") is shown as is; a timestamp is first converted to the company's time zone. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return PLACEHOLDER;
  const dateOnly = DATE_ONLY.exec(value);
  if (dateOnly) return assemble(dateOnly[1], dateOnly[2], dateOnly[3]);
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return PLACEHOLDER;
  const { year, month, day } = zonedParts(date);
  return assemble(year, month, day);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return PLACEHOLDER;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return PLACEHOLDER;
  const { year, month, day, hour, minute } = zonedParts(date);
  return `${assemble(year, month, day)} ${hour}:${minute}`;
}

/** Amounts arrive from the API as decimal strings; they are only formatted here, never used for arithmetic. */
export function formatCurrency(value: string | number, currency: string = config.currency): string {
  const amount = typeof value === "string" ? Number.parseFloat(value) : value;
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(amount);
}
