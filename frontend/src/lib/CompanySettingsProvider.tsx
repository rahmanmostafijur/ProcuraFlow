import type { ReactNode } from "react";

import { useCompanySettings } from "@/api/companySettings";
import { LoadingState } from "@/components/ui/LoadingState";

import { configureFormatting } from "./formatting";
import { useApplyBrandColor } from "./use-brand-color";

/**
 * Loads the company settings for the signed-in app and applies them before anything renders: date pattern,
 * time zone and base currency for every formatted value, and the brand colour. A failed load falls back to
 * the defaults rather than blocking the app.
 */
export function CompanySettingsProvider({ children }: { children: ReactNode }) {
  const { data: settings, isLoading } = useCompanySettings();
  useApplyBrandColor(settings?.brand_color);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <LoadingState label="Loading company settings…" />
      </div>
    );
  }

  if (settings) {
    configureFormatting({
      dateFormat: settings.date_format,
      timeZone: settings.timezone,
      currency: settings.base_currency_code,
    });
  }

  // Re-keying on every saved change re-renders the tree, so values formatted with the old settings refresh too.
  return <div key={settings?.updated_at ?? "defaults"}>{children}</div>;
}
