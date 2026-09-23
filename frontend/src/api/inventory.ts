import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "./client";
import type { InventoryTransaction, PaginatedResponse } from "./types";

export interface InventoryTransactionListParams {
  page: number;
  page_size: number;
  product_id?: number;
}

export function useInventoryTransactions(params: InventoryTransactionListParams) {
  return useQuery({
    queryKey: ["inventory-transactions", params],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<InventoryTransaction>>("/inventory/transactions", {
        params,
      });
      return data;
    },
  });
}

export function useCreateInventoryAdjustment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { product_id: number; quantity_delta: number; reason: string }) => {
      const { data } = await apiClient.post<InventoryTransaction>("/inventory/adjustments", input);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inventory-transactions"] });
      queryClient.invalidateQueries({ queryKey: ["products"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
