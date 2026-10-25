import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "./client";
import type { Currency, ExchangeRate, PaginatedResponse, TaxRate, TaxType } from "./types";

const CURRENCIES_KEY = ["currencies"] as const;
const RATES_KEY = ["exchange-rates"] as const;
const TAX_RATES_KEY = ["tax-rates"] as const;
const REFERENCE_STALE_MS = 5 * 60 * 1000;

export function useCurrencies(activeOnly = false) {
  return useQuery({
    queryKey: [...CURRENCIES_KEY, { activeOnly }],
    queryFn: async () => {
      const { data } = await apiClient.get<Currency[]>("/currencies", { params: { active_only: activeOnly } });
      return data;
    },
    staleTime: REFERENCE_STALE_MS,
  });
}

export interface CurrencyInput {
  code: string;
  name: string;
  symbol: string;
  minor_units: number;
}

export function useCreateCurrency() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: CurrencyInput) => {
      const { data } = await apiClient.post<Currency>("/currencies", input);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CURRENCIES_KEY }),
  });
}

export function useUpdateCurrency() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ code, ...changes }: { code: string; is_active?: boolean; name?: string; symbol?: string }) => {
      const { data } = await apiClient.patch<Currency>(`/currencies/${code}`, changes);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CURRENCIES_KEY }),
  });
}

export function useExchangeRates(params: { page: number; page_size: number; currency_code?: string }) {
  return useQuery({
    queryKey: [...RATES_KEY, params],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<ExchangeRate>>("/exchange-rates", { params });
      return data;
    },
  });
}

export interface ExchangeRateInput {
  currency_code: string;
  rate: string;
  effective_date: string;
}

export function useAddExchangeRate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: ExchangeRateInput) => {
      const { data } = await apiClient.post<ExchangeRate>("/exchange-rates", input);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: RATES_KEY }),
  });
}

export function useDeleteExchangeRate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await apiClient.delete(`/exchange-rates/${id}`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: RATES_KEY }),
  });
}

export function useTaxRates(activeOnly = false) {
  return useQuery({
    queryKey: [...TAX_RATES_KEY, { activeOnly }],
    queryFn: async () => {
      const { data } = await apiClient.get<TaxRate[]>("/tax-rates", { params: { active_only: activeOnly } });
      return data;
    },
    staleTime: REFERENCE_STALE_MS,
  });
}

export interface TaxRateInput {
  name: string;
  percentage: string;
  tax_type: TaxType;
  is_inclusive: boolean;
  is_reverse_charge: boolean;
  region?: string | null;
}

export function useCreateTaxRate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: TaxRateInput) => {
      const { data } = await apiClient.post<TaxRate>("/tax-rates", input);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: TAX_RATES_KEY }),
  });
}

export function useUpdateTaxRate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...changes }: { id: number } & Partial<TaxRateInput> & { is_active?: boolean }) => {
      const { data } = await apiClient.patch<TaxRate>(`/tax-rates/${id}`, changes);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: TAX_RATES_KEY }),
  });
}
