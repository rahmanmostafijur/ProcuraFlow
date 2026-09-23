import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "./client";
import type { PaginatedResponse, POStatus, PurchaseOrder } from "./types";

export interface PurchaseOrderListParams {
  page: number;
  page_size: number;
  status?: POStatus;
  supplier_id?: number;
}

export interface PurchaseOrderItemInput {
  product_id: number;
  quantity: number;
  unit_price: string;
}

export interface PurchaseOrderInput {
  supplier_id: number;
  expected_delivery_date?: string | null;
  notes?: string | null;
  items: PurchaseOrderItemInput[];
}

export function usePurchaseOrders(params: PurchaseOrderListParams) {
  return useQuery({
    queryKey: ["purchase-orders", params],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<PurchaseOrder>>("/purchase-orders", { params });
      return data;
    },
  });
}

export function usePurchaseOrder(id: number | undefined) {
  return useQuery({
    queryKey: ["purchase-orders", id],
    queryFn: async () => {
      const { data } = await apiClient.get<PurchaseOrder>(`/purchase-orders/${id}`);
      return data;
    },
    enabled: id !== undefined,
  });
}

export function useCreatePurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: PurchaseOrderInput) => {
      const { data } = await apiClient.post<PurchaseOrder>("/purchase-orders", input);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["purchase-orders"] }),
  });
}

type Transition = "submit" | "approve" | "order" | "cancel";

export function usePurchaseOrderTransition(transition: Transition) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const { data } = await apiClient.post<PurchaseOrder>(`/purchase-orders/${id}/${transition}`);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useReceivePurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, items }: { id: number; items: { product_id: number; quantity: number }[] }) => {
      const { data } = await apiClient.post<PurchaseOrder>(`/purchase-orders/${id}/receive`, { items });
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
      queryClient.invalidateQueries({ queryKey: ["products"] });
      queryClient.invalidateQueries({ queryKey: ["deliveries"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
