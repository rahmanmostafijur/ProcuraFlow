import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import type { CompanySettings } from "@/api/types";
import { ToastProvider } from "@/components/ui/ToastProvider";

import { CompanySettingsPage } from "./CompanySettingsPage";

const settings: CompanySettings = {
  company_name: "Northbeam Instruments",
  brand_color: "#0F766E",
  logo_url: null,
  legal_name: "Northbeam Instruments Inc.",
  address_line1: "410 Harbor Way",
  address_line2: null,
  city: "Portland",
  region: "OR",
  postal_code: "97209",
  country_code: "US",
  tax_id: null,
  contact_email: null,
  contact_phone: null,
  base_currency_code: "USD",
  fiscal_year_start_month: 1,
  date_format: "MM/DD/YYYY",
  timezone: "America/Los_Angeles",
  po_number_prefix: "PO",
  invoice_tolerance_percent: "2.00",
  default_payment_terms_days: 30,
  updated_at: "2026-10-26T10:00:00Z",
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <CompanySettingsPage />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("CompanySettingsPage", () => {
  beforeEach(() => {
    vi.spyOn(apiClient, "get").mockResolvedValue({ data: settings });
  });

  afterEach(() => vi.restoreAllMocks());

  it("shows the saved settings", async () => {
    renderPage();

    expect(await screen.findByLabelText("Company name")).toHaveValue("Northbeam Instruments");
    expect(screen.getByLabelText("City")).toHaveValue("Portland");
    expect(screen.getByLabelText("Time zone")).toHaveValue("America/Los_Angeles");
  });

  it("saves edited values with codes upper-cased and amounts as decimal strings", async () => {
    const patch = vi.spyOn(apiClient, "patch").mockResolvedValue({ data: { ...settings, po_number_prefix: "NBI" } });
    renderPage();
    const prefix = await screen.findByLabelText("PO number prefix");

    fireEvent.change(prefix, { target: { value: "nbi" } });
    fireEvent.click(screen.getByRole("button", { name: "Save settings" }));

    await waitFor(() => expect(patch).toHaveBeenCalledTimes(1));
    const [url, payload] = patch.mock.calls[0];
    expect(url).toBe("/company-settings");
    expect(payload).toMatchObject({ po_number_prefix: "NBI", invoice_tolerance_percent: "2.00" });
  });

  it("blocks saving an invalid colour and explains why", async () => {
    const patch = vi.spyOn(apiClient, "patch");
    renderPage();
    const colour = await screen.findByLabelText("Brand colour");

    fireEvent.change(colour, { target: { value: "teal" } });
    fireEvent.click(screen.getByRole("button", { name: "Save settings" }));

    expect(await screen.findByText("Use a hex colour such as #0F766E")).toBeInTheDocument();
    expect(patch).not.toHaveBeenCalled();
  });

  it("saves the payer account details used for payment files", async () => {
    const patch = vi.spyOn(apiClient, "patch").mockResolvedValue({ data: settings });
    renderPage();
    expect(await screen.findByRole("heading", { name: "Payer account (for payment files)" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Payer IBAN"), { target: { value: "DE89370400440532013000" } });
    fireEvent.change(screen.getByLabelText("ACH company ID"), { target: { value: "1234567890" } });
    fireEvent.click(screen.getByRole("button", { name: "Save settings" }));

    await waitFor(() => expect(patch).toHaveBeenCalledTimes(1));
    expect(patch.mock.calls[0][1]).toMatchObject({
      payer_iban: "DE89370400440532013000",
      ach_company_id: "1234567890",
      payer_bic: "",
    });
  });
});
