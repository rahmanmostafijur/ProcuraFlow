import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import type { Currency, ExchangeRate, PaginatedResponse, TaxRate } from "@/api/types";
import { ToastProvider } from "@/components/ui/ToastProvider";

import { FinancePage } from "./FinancePage";

const currencies: Currency[] = [
  { code: "USD", name: "US Dollar", symbol: "$", minor_units: 2, is_active: true },
  { code: "EUR", name: "Euro", symbol: "€", minor_units: 2, is_active: true },
  { code: "JPY", name: "Japanese Yen", symbol: "¥", minor_units: 0, is_active: false },
];

const rates: PaginatedResponse<ExchangeRate> = {
  items: [
    {
      id: 5,
      base_currency_code: "USD",
      currency_code: "EUR",
      rate: "1.08000000",
      effective_date: "2026-10-01",
      created_at: "2026-10-01T09:00:00Z",
    },
  ],
  total: 1,
  page: 1,
  page_size: 10,
  total_pages: 1,
};

const taxRates: TaxRate[] = [
  {
    id: 1,
    name: "Germany VAT 19%",
    percentage: "19.0000",
    tax_type: "vat",
    is_inclusive: false,
    is_reverse_charge: false,
    region: "DE",
    is_active: true,
    created_at: "2026-10-01T09:00:00Z",
    updated_at: "2026-10-01T09:00:00Z",
  },
  {
    id: 2,
    name: "EU reverse charge 0%",
    percentage: "0.0000",
    tax_type: "vat",
    is_inclusive: false,
    is_reverse_charge: true,
    region: "EU",
    is_active: false,
    created_at: "2026-10-01T09:00:00Z",
    updated_at: "2026-10-01T09:00:00Z",
  },
];

function respond(url: string, params?: { active_only?: boolean }): unknown {
  if (url === "/currencies")
    return params?.active_only ? currencies.filter((currency) => currency.is_active) : currencies;
  if (url === "/exchange-rates") return rates;
  if (url === "/tax-rates") return taxRates;
  if (url === "/company-settings") return { base_currency_code: "USD", timezone: "UTC" };
  throw new Error(`unexpected GET ${url}`);
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <FinancePage />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("FinancePage", () => {
  beforeEach(() => {
    vi.spyOn(apiClient, "get").mockImplementation((url, config) =>
      Promise.resolve({ data: respond(url, config?.params as { active_only?: boolean } | undefined) }),
    );
  });

  afterEach(() => vi.restoreAllMocks());

  it("lists currencies, rates and tax rates, and marks the base currency", async () => {
    renderPage();

    const usd = (await screen.findByText("US Dollar")).closest("tr") as HTMLElement;
    expect(within(usd).getByText("Base currency")).toBeInTheDocument();
    expect(within(usd).queryByRole("button")).not.toBeInTheDocument();
    expect(await screen.findByText("1.08000000")).toBeInTheDocument();
    expect(screen.getByText("Germany VAT 19%")).toBeInTheDocument();
    const reverseCharge = screen.getByText("EU reverse charge 0%").closest("tr") as HTMLElement;
    expect(within(reverseCharge).getByText("Reverse charge")).toBeInTheDocument();
    expect(within(reverseCharge).getByText("Retired")).toBeInTheDocument();
  });

  it("switches a currency on", async () => {
    const patch = vi.spyOn(apiClient, "patch").mockResolvedValue({ data: currencies[2] });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Switch on JPY" }));

    await waitFor(() => expect(patch).toHaveBeenCalledWith("/currencies/JPY", { is_active: true }));
  });

  it("saves a rate with the date and the decimal string as typed", async () => {
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: rates.items[0] });
    renderPage();
    await screen.findByText("US Dollar");

    fireEvent.change(screen.getByLabelText("Currency"), { target: { value: "EUR" } });
    fireEvent.change(screen.getByLabelText("Rate (USD per 1)"), { target: { value: "1.0834" } });
    fireEvent.change(screen.getByLabelText("Effective from"), { target: { value: "2026-10-26" } });
    fireEvent.click(screen.getByRole("button", { name: /Save rate/ }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/exchange-rates", {
        currency_code: "EUR",
        rate: "1.0834",
        effective_date: "2026-10-26",
      }),
    );
  });

  it("does not offer the base currency when entering a rate", async () => {
    renderPage();
    await screen.findByText("US Dollar");

    const options = within(screen.getByLabelText("Currency")).getAllByRole("option");

    expect(options.map((option) => option.textContent)).toEqual(["Choose…", "EUR — Euro"]);
  });

  it("rejects a rate that is not a positive number", async () => {
    const post = vi.spyOn(apiClient, "post");
    renderPage();
    await screen.findByText("US Dollar");

    fireEvent.change(screen.getByLabelText("Currency"), { target: { value: "EUR" } });
    fireEvent.change(screen.getByLabelText("Rate (USD per 1)"), { target: { value: "0" } });
    fireEvent.click(screen.getByRole("button", { name: /Save rate/ }));

    expect(await screen.findByText("Must be greater than 0")).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();
  });

  it("creates a reverse-charge tax rate only at 0%", async () => {
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: taxRates[1] });
    renderPage();
    await screen.findByText("Germany VAT 19%");

    fireEvent.change(screen.getByLabelText("Tax rate name"), { target: { value: "Reverse" } });
    fireEvent.change(screen.getByLabelText("Rate (%)"), { target: { value: "5" } });
    fireEvent.change(screen.getByLabelText("Treatment"), { target: { value: "reverse_charge" } });
    fireEvent.click(screen.getByRole("button", { name: /Add tax rate/ }));
    expect(await screen.findByText("Reverse charge is always 0%")).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Rate (%)"), { target: { value: "0" } });
    fireEvent.click(screen.getByRole("button", { name: /Add tax rate/ }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/tax-rates", {
        name: "Reverse",
        percentage: "0",
        tax_type: "vat",
        is_inclusive: false,
        is_reverse_charge: true,
        region: null,
      }),
    );
  });

  it("retires a tax rate", async () => {
    const patch = vi.spyOn(apiClient, "patch").mockResolvedValue({ data: taxRates[0] });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Retire Germany VAT 19%" }));

    await waitFor(() => expect(patch).toHaveBeenCalledWith("/tax-rates/1", { is_active: false }));
  });
});
