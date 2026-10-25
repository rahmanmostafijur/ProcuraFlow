import { z } from "zod";

import type { CompanySettingsInput } from "@/api/companySettings";
import type { CompanySettings, DateFormat } from "@/api/types";

export const DATE_FORMATS: { value: DateFormat; example: string }[] = [
  { value: "MM/DD/YYYY", example: "03/15/2026" },
  { value: "DD/MM/YYYY", example: "15/03/2026" },
  { value: "DD.MM.YYYY", example: "15.03.2026" },
  { value: "YYYY-MM-DD", example: "2026-03-15" },
];

export const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

const optionalText = (max: number) => z.string().trim().max(max, `At most ${max} characters`);

// Mirrors the API's rules so mistakes show next to the field; the API validates again either way.
export const settingsSchema = z.object({
  company_name: z.string().trim().min(1, "Company name is required").max(200),
  legal_name: optionalText(200),
  address_line1: optionalText(200),
  address_line2: optionalText(200),
  city: optionalText(100),
  region: optionalText(100),
  postal_code: optionalText(20),
  country_code: z
    .string()
    .trim()
    .regex(/^([A-Za-z]{2})?$/, "Use a two-letter country code, e.g. US or DE"),
  tax_id: optionalText(50),
  contact_email: z.union([z.literal(""), z.string().trim().email("Enter a valid email address")]),
  contact_phone: optionalText(50),
  brand_color: z.string().regex(/^#[0-9A-Fa-f]{6}$/, "Use a hex colour such as #0F766E"),
  base_currency_code: z
    .string()
    .trim()
    .regex(/^[A-Za-z]{3}$/, "Use a three-letter ISO currency code"),
  fiscal_year_start_month: z.coerce.number().int().min(1).max(12),
  date_format: z.enum(["YYYY-MM-DD", "MM/DD/YYYY", "DD/MM/YYYY", "DD.MM.YYYY"]),
  timezone: z.string().min(1, "Choose a time zone"),
  po_number_prefix: z
    .string()
    .trim()
    .regex(/^[A-Za-z0-9]{1,10}$/, "1 to 10 letters or digits"),
  invoice_tolerance_percent: z.coerce
    .number({ invalid_type_error: "Enter a percentage" })
    .min(0, "0 or more")
    .max(100, "100 or less")
    .multipleOf(0.01, "At most two decimals"),
  default_payment_terms_days: z.coerce.number().int("Whole days only").min(0).max(365),
});

export type SettingsFormValues = z.infer<typeof settingsSchema>;

export function toFormValues(settings: CompanySettings): SettingsFormValues {
  return {
    company_name: settings.company_name,
    legal_name: settings.legal_name ?? "",
    address_line1: settings.address_line1 ?? "",
    address_line2: settings.address_line2 ?? "",
    city: settings.city ?? "",
    region: settings.region ?? "",
    postal_code: settings.postal_code ?? "",
    country_code: settings.country_code ?? "",
    tax_id: settings.tax_id ?? "",
    contact_email: settings.contact_email ?? "",
    contact_phone: settings.contact_phone ?? "",
    brand_color: settings.brand_color,
    base_currency_code: settings.base_currency_code,
    fiscal_year_start_month: settings.fiscal_year_start_month,
    date_format: settings.date_format,
    timezone: settings.timezone,
    po_number_prefix: settings.po_number_prefix,
    invoice_tolerance_percent: Number(settings.invoice_tolerance_percent),
    default_payment_terms_days: settings.default_payment_terms_days,
  };
}

/** Empty optional fields are sent as empty strings, which the API stores as "not set". */
export function toPayload(values: SettingsFormValues): CompanySettingsInput {
  return {
    ...values,
    country_code: values.country_code.toUpperCase(),
    base_currency_code: values.base_currency_code.toUpperCase(),
    po_number_prefix: values.po_number_prefix.toUpperCase(),
    invoice_tolerance_percent: values.invoice_tolerance_percent.toFixed(2),
  };
}

export function timeZoneOptions(current: string): string[] {
  const zones = typeof Intl.supportedValuesOf === "function" ? Intl.supportedValuesOf("timeZone") : [];
  return zones.includes(current) ? zones : [current, ...zones];
}
