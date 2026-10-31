import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "./client";
import type { PaginatedResponse, POStatus, PurchaseOrder, PurchaseOrderVersion } from "./types";

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
  tax_rate_id?: number | null;
}

export interface PurchaseOrderInput {
  supplier_id: number;
  cost_centre_id?: number | null;
  // Omitted: the supplier's default currency, else the company's base currency.
  currency_code?: string | null;
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
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: ["purchase-orders"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
      ]),
  });
}

/** The PDF endpoint needs the bearer token, so it is fetched through the client rather than linked to. */
export async function fetchPurchaseOrderPdf(id: number): Promise<Blob> {
  const { data } = await apiClient.get<Blob>(`/purchase-orders/${id}/pdf`, { responseType: "blob" });
  return data;
}

export function useSendPurchaseOrder() {
  return useMutation({
    mutationFn: async (id: number) => {
      await apiClient.post(`/purchase-orders/${id}/send`);
    },
  });
}

export function useRejectPurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, comment }: { id: number; comment: string }) => {
      const { data } = await apiClient.post<PurchaseOrder>(`/purchase-orders/${id}/reject`, { comment });
      return data;
    },
    onSuccess: () =>
      Promise.all(
        ["purchase-orders", "approvals", "dashboard"].map((key) => queryClient.invalidateQueries({ queryKey: [key] })),
      ),
  });
}

export function usePurchaseOrderVersions(id: number | undefined) {
  return useQuery({
    queryKey: ["purchase-orders", id, "versions"],
    queryFn: async () => {
      const { data } = await apiClient.get<PurchaseOrderVersion[]>(`/purchase-orders/${id}/versions`);
      return data;
    },
    enabled: id !== undefined,
  });
}

export interface AmendInput {
  reason: string;
  items?: PurchaseOrderItemInput[];
  expected_delivery_date?: string | null;
  notes?: string | null;
}

export function useAmendPurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...input }: AmendInput & { id: number }) => {
      const { data } = await apiClient.post<PurchaseOrderVersion>(`/purchase-orders/${id}/amend`, input);
      return data;
    },
    onSuccess: () =>
      Promise.all(
        ["purchase-orders", "approvals", "dashboard", "deliveries"].map((key) =>
          queryClient.invalidateQueries({ queryKey: [key] }),
        ),
      ),
  });
}

export function useWithdrawAmendment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (versionId: number) => {
      const { data } = await apiClient.post<PurchaseOrderVersion>(`/po-amendments/${versionId}/withdraw`);
      return data;
    },
    onSuccess: () =>
      Promise.all(["purchase-orders", "approvals"].map((key) => queryClient.invalidateQueries({ queryKey: [key] }))),
  });
}

export function useReceivePurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, items }: { id: number; items: { product_id: number; quantity: number }[] }) => {
      const { data } = await apiClient.post<PurchaseOrder>(`/purchase-orders/${id}/receive`, { items });
      return data;
    },
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: ["purchase-orders"] }),
        queryClient.invalidateQueries({ queryKey: ["products"] }),
        queryClient.invalidateQueries({ queryKey: ["deliveries"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
      ]),
  });
}
