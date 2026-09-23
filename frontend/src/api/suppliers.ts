import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "./client";
import type { PaginatedResponse, Supplier } from "./types";

export interface SupplierListParams {
  page: number;
  page_size: number;
  search?: string;
  is_active?: boolean;
}

export interface SupplierInput {
  name: string;
  contact_name?: string | null;
  email?: string | null;
  phone?: string | null;
  address?: string | null;
}

export function useSuppliers(params: SupplierListParams) {
  return useQuery({
    queryKey: ["suppliers", params],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<Supplier>>("/suppliers", { params });
      return data;
    },
  });
}

export function useCreateSupplier() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: SupplierInput) => {
      const { data } = await apiClient.post<Supplier>("/suppliers", input);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["suppliers"] }),
  });
}

export function useUpdateSupplier() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...input }: Partial<SupplierInput> & { id: number; is_active?: boolean }) => {
      const { data } = await apiClient.patch<Supplier>(`/suppliers/${id}`, input);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["suppliers"] }),
  });
}
