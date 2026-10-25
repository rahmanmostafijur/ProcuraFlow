import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "./client";
import type { CatalogItem } from "./types";

export interface CatalogParams {
  search?: string;
  supplier_id?: number;
  active_only?: boolean;
}

export function useCatalog(params: CatalogParams = {}) {
  return useQuery({
    queryKey: ["catalog", params],
    queryFn: async () => {
      const { data } = await apiClient.get<CatalogItem[]>("/catalog-items", { params });
      return data;
    },
  });
}

export interface CatalogItemInput {
  product_id: number;
  supplier_id: number;
  contract_price: string;
  currency_code?: string | null;
  lead_time_days: number;
  valid_from?: string | null;
  valid_until?: string | null;
}

export function useSaveCatalogItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...input }: { id?: number } & Partial<CatalogItemInput> & { is_active?: boolean }) => {
      const { data } =
        id === undefined
          ? await apiClient.post<CatalogItem>("/catalog-items", input)
          : await apiClient.patch<CatalogItem>(`/catalog-items/${id}`, input);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["catalog"] }),
  });
}
