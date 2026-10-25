import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "./client";
import type { ApprovalDocumentType, ApprovalLimit, ApprovalRule, ApprovalStep, Delegation, QueuePage } from "./types";

const QUEUE_REFRESH_MS = 60_000;

/** Everything waiting for the signed-in user. The sidebar badge reads `total` from the same list. */
export function useApprovalQueue(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: ["approvals", "queue", page, pageSize],
    queryFn: async () => {
      const { data } = await apiClient.get<QueuePage>("/approvals/queue", { params: { page, page_size: pageSize } });
      return data;
    },
    refetchInterval: QUEUE_REFRESH_MS,
  });
}

export function useApprovalHistory(documentType: ApprovalDocumentType, documentId: number | undefined) {
  return useQuery({
    queryKey: ["approvals", "steps", documentType, documentId],
    queryFn: async () => {
      const { data } = await apiClient.get<ApprovalStep[]>(`/approvals/${documentType}/${documentId}/steps`);
      return data;
    },
    enabled: documentId !== undefined,
  });
}

function useApprovalsInvalidation() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all(
      ["approvals", "requests", "purchase-orders", "dashboard"].map((key) =>
        queryClient.invalidateQueries({ queryKey: [key] }),
      ),
    );
}

/** Approve or reject any kind of document from the queue. */
export function useDecide() {
  const invalidate = useApprovalsInvalidation();
  return useMutation({
    mutationFn: async ({
      documentType,
      documentId,
      approve,
      comment,
    }: {
      documentType: ApprovalDocumentType;
      documentId: number;
      approve: boolean;
      comment?: string;
    }) => {
      const base =
        documentType === "purchase_request"
          ? `/purchase-requests/${documentId}`
          : documentType === "purchase_order"
            ? `/purchase-orders/${documentId}`
            : `/po-amendments/${documentId}`;
      await apiClient.post(`${base}/${approve ? "approve" : "reject"}`, comment ? { comment } : undefined);
    },
    onSuccess: invalidate,
  });
}

export function useApprovalRules() {
  return useQuery({
    queryKey: ["approvals", "rules"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApprovalRule[]>("/approval-rules");
      return data;
    },
  });
}

export interface ApprovalRuleInput {
  name: string;
  document_type: ApprovalDocumentType;
  min_amount: string;
  max_amount: string | null;
  is_active: boolean;
  steps: { approver_role_id: number }[];
}

export function useSaveRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...input }: Partial<ApprovalRuleInput> & { id?: number }) => {
      const { data } =
        id === undefined
          ? await apiClient.post<ApprovalRule>("/approval-rules", input)
          : await apiClient.patch<ApprovalRule>(`/approval-rules/${id}`, input);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["approvals", "rules"] }),
  });
}

export function useDeleteRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await apiClient.delete(`/approval-rules/${id}`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["approvals", "rules"] }),
  });
}

export function useApprovalLimits() {
  return useQuery({
    queryKey: ["approvals", "limits"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApprovalLimit[]>("/approval-limits");
      return data;
    },
  });
}

export function useSetLimit() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { user_id: number; document_type: ApprovalDocumentType; max_amount: string }) => {
      const { data } = await apiClient.put<ApprovalLimit>("/approval-limits", input);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["approvals", "limits"] }),
  });
}

export function useRemoveLimit() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await apiClient.delete(`/approval-limits/${id}`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["approvals", "limits"] }),
  });
}

export function useDelegations() {
  return useQuery({
    queryKey: ["approvals", "delegations"],
    queryFn: async () => {
      const { data } = await apiClient.get<Delegation[]>("/approval-delegations");
      return data;
    },
  });
}

export function useCreateDelegation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { delegate_id: number; starts_on: string; ends_on: string; delegator_id?: number }) => {
      const { data } = await apiClient.post<Delegation>("/approval-delegations", input);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["approvals"] }),
  });
}

export function useRevokeDelegation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const { data } = await apiClient.post<Delegation>(`/approval-delegations/${id}/revoke`);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["approvals"] }),
  });
}
