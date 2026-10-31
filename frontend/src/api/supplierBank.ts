import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "./client";

export interface BankDetails {
  id: number;
  supplier_id: number;
  status: string;
  bank_account_name: string | null;
  bank_country: string | null;
  iban: string | null;
  bic: string | null;
  bank_account_number: string | null;
  routing_number: string | null;
  requested_by: { id: number; full_name: string };
  requested_at: string;
  decided_by: { id: number; full_name: string } | null;
  decided_at: string | null;
  decision_comment: string | null;
  superseded_at: string | null;
}

export interface BankDetailsOverview {
  current: BankDetails | null;
  pending: BankDetails | null;
  history: BankDetails[];
}

export interface BankChangeInput {
  bank_account_name: string;
  bank_country: string;
  iban?: string;
  bic?: string;
  bank_account_number?: string;
  routing_number?: string;
}

const key = (supplierId: number) => ["supplier-bank", supplierId] as const;

export function useBankDetails(supplierId: number) {
  return useQuery({
    queryKey: key(supplierId),
    queryFn: async () => {
      const { data } = await apiClient.get<BankDetailsOverview>(`/suppliers/${supplierId}/bank-details`);
      return data;
    },
  });
}

export function useRequestBankChange(supplierId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: BankChangeInput) => {
      const { data } = await apiClient.post<BankDetails>(`/suppliers/${supplierId}/bank-details/changes`, input);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key(supplierId) }),
  });
}

export function useDecideBankChange(supplierId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      changeId,
      decision,
      comment,
    }: {
      changeId: number;
      decision: "approve" | "reject";
      comment?: string;
    }) => {
      const { data } = await apiClient.post<BankDetails>(
        `/suppliers/${supplierId}/bank-details/changes/${changeId}/${decision}`,
        { comment: comment || null },
      );
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key(supplierId) }),
  });
}

/** Account numbers are shown masked: only the last four characters stay visible. */
export function maskIdentifier(value: string | null): string {
  if (!value) return "—";
  const visible = value.slice(-4);
  return `${"•".repeat(Math.max(value.length - 4, 0))}${visible}`;
}
