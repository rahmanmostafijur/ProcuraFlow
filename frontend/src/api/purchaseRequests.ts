import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "./client";
import type { PaginatedResponse, PurchaseRequest, PurchaseRequestStatus } from "./types";

export interface RequestLineInput {
  description: string;
  quantity: number;
  unit?: string;
  estimated_unit_price?: string | null;
  catalog_item_id?: number | null;
  product_id?: number | null;
  supplier_id?: number | null;
}

export interface PurchaseRequestInput {
  title: string;
  notes?: string | null;
  cost_centre_id?: number | null;
  currency_code?: string | null;
  needed_by?: string | null;
  lines: RequestLineInput[];
}

export interface RequestListParams {
  page: number;
  page_size: number;
  status?: PurchaseRequestStatus;
  mine?: boolean;
}

export interface ConvertInput {
  orders: {
    supplier_id: number;
    expected_delivery_date?: string | null;
    notes?: string | null;
    lines: { line_id: number; product_id?: number | null; unit_price?: string | null }[];
  }[];
}

export function useRequests(params: RequestListParams) {
  return useQuery({
    queryKey: ["requests", params],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<PurchaseRequest>>("/purchase-requests", { params });
      return data;
    },
  });
}

export function useRequest(id: number | undefined) {
  return useQuery({
    queryKey: ["requests", id],
    queryFn: async () => {
      const { data } = await apiClient.get<PurchaseRequest>(`/purchase-requests/${id}`);
      return data;
    },
    enabled: id !== undefined,
  });
}

/** Anything that changes a request also changes what is waiting for someone, so both lists refresh. */
function useRequestMutation<TInput>(request: (input: TInput) => Promise<PurchaseRequest>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: request,
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: ["requests"] }),
        queryClient.invalidateQueries({ queryKey: ["approvals"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
      ]),
  });
}

export function useCreateRequest() {
  return useRequestMutation(async (input: PurchaseRequestInput) => {
    const { data } = await apiClient.post<PurchaseRequest>("/purchase-requests", input);
    return data;
  });
}

export function useUpdateRequest() {
  return useRequestMutation(async ({ id, ...input }: Partial<PurchaseRequestInput> & { id: number }) => {
    const { data } = await apiClient.patch<PurchaseRequest>(`/purchase-requests/${id}`, input);
    return data;
  });
}

export function useRequestAction(action: "submit" | "cancel" | "approve") {
  return useRequestMutation(async ({ id, comment }: { id: number; comment?: string }) => {
    const { data } = await apiClient.post<PurchaseRequest>(
      `/purchase-requests/${id}/${action}`,
      comment ? { comment } : undefined,
    );
    return data;
  });
}

export function useRejectRequest() {
  return useRequestMutation(async ({ id, comment }: { id: number; comment: string }) => {
    const { data } = await apiClient.post<PurchaseRequest>(`/purchase-requests/${id}/reject`, { comment });
    return data;
  });
}

export function useConvertRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...input }: ConvertInput & { id: number }) => {
      const { data } = await apiClient.post<{ purchase_order_ids: number[]; request: PurchaseRequest }>(
        `/purchase-requests/${id}/convert`,
        input,
      );
      return data;
    },
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: ["requests"] }),
        queryClient.invalidateQueries({ queryKey: ["purchase-orders"] }),
      ]),
  });
}
