import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";

import { apiClient } from "./client";
import { downloadFile } from "./downloads";
import type { PaginatedResponse } from "./types";

export type PaymentRunStatus = "draft" | "released" | "cancelled";

export interface PaymentRunItem {
  id: number;
  invoice_id: number;
  invoice_number: string;
  supplier_id: number;
  supplier_name: string;
  amount: string;
}

export interface PaymentRun {
  id: number;
  number: string;
  status: PaymentRunStatus;
  method: string;
  currency_code: string;
  total: string;
  creator: { id: number; full_name: string };
  releaser: { id: number; full_name: string } | null;
  released_at: string | null;
  created_at: string;
  items: PaymentRunItem[];
}

export interface PaymentFile {
  id: number;
  run_id: number;
  run_number: string;
  file_format: "sepa_pain001" | "nacha_ach";
  filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  currency_code: string;
  transaction_count: number;
  total: string;
  created_by: { id: number; full_name: string };
  created_at: string;
}

export const FILE_FORMAT_LABELS: Record<PaymentFile["file_format"], string> = {
  sepa_pain001: "SEPA credit transfer (pain.001)",
  nacha_ach: "NACHA / ACH",
};

const RUNS_KEY = ["payment-runs"] as const;

export function usePaymentRuns(page: number, pageSize: number) {
  return useQuery({
    queryKey: [...RUNS_KEY, "list", page, pageSize],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<PaymentRun>>("/payment-runs", {
        params: { page, page_size: pageSize },
      });
      return data;
    },
  });
}

function useRunAction(action: "release" | "cancel") {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (runId: number) => {
      const { data } = await apiClient.post<PaymentRun>(`/payment-runs/${runId}/${action}`);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: RUNS_KEY }),
  });
}

export const useReleasePaymentRun = () => useRunAction("release");
export const useCancelPaymentRun = () => useRunAction("cancel");

/** The file is generated once; a run that has none yet answers 404, which simply means "not generated". */
export function usePaymentFile(runId: number, enabled: boolean) {
  return useQuery({
    queryKey: [...RUNS_KEY, "file", runId],
    enabled,
    retry: false,
    queryFn: async () => {
      try {
        const { data } = await apiClient.get<PaymentFile>(`/payment-runs/${runId}/file`);
        return data;
      } catch (error) {
        if (axios.isAxiosError(error) && error.response?.status === 404) return null;
        throw error;
      }
    },
  });
}

export function useGeneratePaymentFile(runId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.post<PaymentFile>(`/payment-runs/${runId}/file`);
      return data;
    },
    onSuccess: (file) => queryClient.setQueryData([...RUNS_KEY, "file", runId], file),
  });
}

export function downloadPaymentFile(file: PaymentFile): Promise<void> {
  return downloadFile(`/payment-runs/${file.run_id}/file/download`, file.filename);
}

/** The API refuses with one sentence: "Cannot export RUN-1: a | b". Splits it into the list of problems. */
export function parseExportProblems(detail: string): string[] {
  const separator = detail.indexOf(": ");
  const list = detail.includes(" | ") || separator >= 0 ? detail.slice(separator + 2) : detail;
  return list
    .split(" | ")
    .map((problem) => problem.trim())
    .filter(Boolean);
}
