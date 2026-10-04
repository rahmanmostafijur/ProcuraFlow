import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "./client";
import type { PaginatedResponse, Product } from "./types";

export interface ProductListParams {
  page: number;
  page_size: number;
  search?: string;
  category_id?: number;
  supplier_id?: number;
  is_active?: boolean;
  low_stock_only?: boolean;
}

export interface ProductInput {
  sku: string;
  name: string;
  category_id?: number | null;
  unit: string;
  cost: string;
  minimum_stock: number;
  supplier_id?: number | null;
}

export function useProducts(params: ProductListParams) {
  return useQuery({
    queryKey: ["products", params],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<Product>>("/products", { params });
      return data;
    },
  });
}

export function useCreateProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: ProductInput) => {
      const { data } = await apiClient.post<Product>("/products", input);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["products"] }),
  });
}

export function useUpdateProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...input }: Partial<ProductInput> & { id: number; is_active?: boolean }) => {
      const { data } = await apiClient.patch<Product>(`/products/${id}`, input);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["products"] }),
  });
}
