import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "./client";
import type { BudgetChange, BudgetPosition, BudgetTransfer, CostCentre } from "./types";

export function useCostCentres(activeOnly = false) {
  return useQuery({
    queryKey: ["budgets", "cost-centres", { activeOnly }],
    queryFn: async () => {
      const { data } = await apiClient.get<CostCentre[]>("/cost-centres", { params: { active_only: activeOnly } });
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });
}

export function useSaveCostCentre() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      ...input
    }: { id?: number } & Partial<{ code: string; name: string; manager_id: number | null; is_active: boolean }>) => {
      const { data } =
        id === undefined
          ? await apiClient.post<CostCentre>("/cost-centres", input)
          : await apiClient.patch<CostCentre>(`/cost-centres/${id}`, input);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["budgets"] }),
  });
}

export function useBudgetPositions(fiscalYear?: number) {
  return useQuery({
    queryKey: ["budgets", "positions", fiscalYear ?? "current"],
    queryFn: async () => {
      const { data } = await apiClient.get<BudgetPosition[]>("/budgets", { params: { fiscal_year: fiscalYear } });
      return data;
    },
  });
}

export function useSetBudget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { cost_centre_id: number; fiscal_year: number; amount: string; reason?: string }) => {
      const { data } = await apiClient.put<BudgetPosition>("/budgets", input);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["budgets"] }),
  });
}

export function useBudgetHistory(budgetId: number | undefined) {
  return useQuery({
    queryKey: ["budgets", "history", budgetId],
    queryFn: async () => {
      const { data } = await apiClient.get<BudgetChange[]>(`/budgets/${budgetId}/history`);
      return data;
    },
    enabled: budgetId !== undefined,
  });
}

export function useTransfers() {
  return useQuery({
    queryKey: ["budgets", "transfers"],
    queryFn: async () => {
      const { data } = await apiClient.get<BudgetTransfer[]>("/budget-transfers");
      return data;
    },
  });
}

export function useRequestTransfer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { from_budget_id: number; to_budget_id: number; amount: string; reason: string }) => {
      const { data } = await apiClient.post<BudgetTransfer>("/budget-transfers", input);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["budgets"] }),
  });
}

export function useDecideTransfer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, approve, comment }: { id: number; approve: boolean; comment?: string }) => {
      const { data } = await apiClient.post<BudgetTransfer>(
        `/budget-transfers/${id}/${approve ? "approve" : "reject"}`,
        comment ? { comment } : undefined,
      );
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["budgets"] }),
  });
}
