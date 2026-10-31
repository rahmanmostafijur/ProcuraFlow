import { zodResolver } from "@hookform/resolvers/zod";
import type { ReactNode } from "react";
import { useForm, useWatch } from "react-hook-form";

import { extractErrorMessage } from "@/api/client";
import { useCompanySettings, useUpdateCompanySettings } from "@/api/companySettings";
import type { CompanySettings } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { LoadingState } from "@/components/ui/LoadingState";
import { Select } from "@/components/ui/Select";
import { useToast } from "@/components/ui/toast-context";

import { LogoUploader } from "./LogoUploader";
import {
  DATE_FORMATS,
  MONTHS,
  type SettingsFormValues,
  settingsSchema,
  timeZoneOptions,
  toFormValues,
  toPayload,
} from "./settingsSchema";

function Section({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <Card className="p-6">
      <div className="mb-4">
        <h2 className="text-base font-semibold text-slate-900">{title}</h2>
        <p className="text-sm text-slate-500">{description}</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">{children}</div>
    </Card>
  );
}

function Field({ id, label, children, wide }: { id: string; label: string; children: ReactNode; wide?: boolean }) {
  return (
    <div className={wide ? "sm:col-span-2" : undefined}>
      <Label htmlFor={id}>{label}</Label>
      {children}
    </div>
  );
}

function SettingsForm({ settings }: { settings: CompanySettings }) {
  const { showToast } = useToast();
  const updateSettings = useUpdateCompanySettings();
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    control,
    formState: { errors, isDirty },
  } = useForm<SettingsFormValues>({ resolver: zodResolver(settingsSchema), defaultValues: toFormValues(settings) });
  const brandColor = useWatch({ control, name: "brand_color" });

  const onSubmit = async (values: SettingsFormValues) => {
    try {
      const saved = await updateSettings.mutateAsync(toPayload(values));
      reset(toFormValues(saved));
      showToast("Settings saved");
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  const text = (name: keyof SettingsFormValues, label: string, wide = false) => (
    <Field id={name} label={label} wide={wide}>
      <Input id={name} error={errors[name]?.message} {...register(name)} />
    </Field>
  );

  return (
    <form className="space-y-6" onSubmit={(event) => void handleSubmit(onSubmit)(event)}>
      <Section title="Company" description="Shown on purchase orders, emails and the sign-in page.">
        {text("company_name", "Company name")}
        {text("legal_name", "Legal name")}
        {text("tax_id", "Tax / VAT ID")}
        {text("contact_email", "Billing contact email")}
        {text("contact_phone", "Phone")}
        {text("address_line1", "Address line 1", true)}
        {text("address_line2", "Address line 2", true)}
        {text("city", "City")}
        {text("region", "State / region")}
        {text("postal_code", "Postal code")}
        {text("country_code", "Country code")}
      </Section>

      <Section title="Branding" description="Your logo and colour replace the ProcuraFlow defaults everywhere.">
        <div className="sm:col-span-2">
          <LogoUploader settings={settings} />
        </div>
        <Field id="brand_color" label="Brand colour">
          <div className="flex items-center gap-2">
            <input
              type="color"
              aria-label="Pick brand colour"
              className="h-9 w-12 cursor-pointer rounded border border-slate-300"
              value={/^#[0-9A-Fa-f]{6}$/.test(brandColor) ? brandColor : "#000000"}
              onChange={(event) =>
                setValue("brand_color", event.target.value.toUpperCase(), { shouldDirty: true, shouldValidate: true })
              }
            />
            <Input id="brand_color" error={errors.brand_color?.message} {...register("brand_color")} />
          </div>
        </Field>
      </Section>

      <Section title="Regional" description="How dates and amounts are shown, and which currency reports use.">
        {text("base_currency_code", "Base currency")}
        <Field id="date_format" label="Date format">
          <Select id="date_format" {...register("date_format")}>
            {DATE_FORMATS.map((format) => (
              <option key={format.value} value={format.value}>
                {format.value} ({format.example})
              </option>
            ))}
          </Select>
        </Field>
        <Field id="timezone" label="Time zone">
          <Select id="timezone" error={errors.timezone?.message} {...register("timezone")}>
            {timeZoneOptions(settings.timezone).map((zone) => (
              <option key={zone} value={zone}>
                {zone}
              </option>
            ))}
          </Select>
        </Field>
        <Field id="fiscal_year_start_month" label="Fiscal year starts in">
          <Select id="fiscal_year_start_month" {...register("fiscal_year_start_month")}>
            {MONTHS.map((month, index) => (
              <option key={month} value={index + 1}>
                {month}
              </option>
            ))}
          </Select>
        </Field>
      </Section>

      <Section title="Purchasing" description="Defaults for new orders and supplier invoices.">
        {text("po_number_prefix", "PO number prefix")}
        {text("default_payment_terms_days", "Default payment terms (days)")}
        {text("invoice_tolerance_percent", "Invoice match tolerance (%)")}
      </Section>

      <Section
        title="Payer account (for payment files)"
        description="Your own bank details, written into the SEPA and ACH files. Suppliers' details are kept on each supplier."
      >
        {text("payer_iban", "Payer IBAN")}
        {text("payer_bic", "Payer BIC")}
        {text("payer_routing_number", "Payer routing number")}
        {text("payer_account_number", "Payer account number")}
        {text("ach_company_id", "ACH company ID")}
      </Section>

      <div className="flex justify-end gap-2">
        <Button type="button" variant="secondary" disabled={!isDirty} onClick={() => reset(toFormValues(settings))}>
          Discard changes
        </Button>
        <Button type="submit" disabled={!isDirty || updateSettings.isPending}>
          {updateSettings.isPending ? "Saving…" : "Save settings"}
        </Button>
      </div>
    </form>
  );
}

export function CompanySettingsPage() {
  const { data: settings, isLoading, isError } = useCompanySettings();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Company settings</h1>
        <p className="text-sm text-slate-500">Branding, regional preferences and purchasing defaults.</p>
      </div>
      {isLoading && <LoadingState />}
      {isError && <ErrorState message="The settings could not be loaded. Reload the page to try again." />}
      {settings && <SettingsForm settings={settings} />}
    </div>
  );
}
