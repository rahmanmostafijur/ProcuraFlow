import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { API_BASE_URL, apiClient } from "./client";
import type { Branding, CompanySettings } from "./types";

const SETTINGS_KEY = ["company-settings"] as const;
const BRANDING_KEY = ["company-settings", "branding"] as const;

export type CompanySettingsInput = Partial<Omit<CompanySettings, "logo_url" | "updated_at">>;

/** The API returns the logo path relative to its own root; the browser needs the full address. */
export function absoluteLogoUrl(logoUrl: string | null): string | null {
  return logoUrl ? `${API_BASE_URL}${logoUrl}` : null;
}

export function useBranding(enabled = true) {
  return useQuery({
    queryKey: BRANDING_KEY,
    queryFn: async () => {
      const { data } = await apiClient.get<Branding>("/company-settings/branding");
      return data;
    },
    enabled,
    staleTime: 5 * 60 * 1000,
  });
}

export function useCompanySettings(enabled = true) {
  return useQuery({
    queryKey: SETTINGS_KEY,
    queryFn: async () => {
      const { data } = await apiClient.get<CompanySettings>("/company-settings");
      return data;
    },
    enabled,
    staleTime: 5 * 60 * 1000,
  });
}

function useSettingsMutation<TInput>(request: (input: TInput) => Promise<CompanySettings>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: request,
    onSuccess: (settings) => {
      queryClient.setQueryData(SETTINGS_KEY, settings);
      void queryClient.invalidateQueries({ queryKey: BRANDING_KEY });
    },
  });
}

export function useUpdateCompanySettings() {
  return useSettingsMutation(async (input: CompanySettingsInput) => {
    const { data } = await apiClient.patch<CompanySettings>("/company-settings", input);
    return data;
  });
}

export function useUploadLogo() {
  return useSettingsMutation(async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const { data } = await apiClient.put<CompanySettings>("/company-settings/logo", form);
    return data;
  });
}

export function useRemoveLogo() {
  return useSettingsMutation(async () => {
    const { data } = await apiClient.delete<CompanySettings>("/company-settings/logo");
    return data;
  });
}
