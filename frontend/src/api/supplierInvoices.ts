import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "./client";
import type { PaginatedResponse, Person } from "./types";

export type InvoiceStatus = "draft" | "matched" | "exception" | "approved" | "on_hold" | "paid" | "void";
export type InvoiceMatchMode = "three_way" | "two_way";
export type PaymentMethod = "bank_transfer" | "card" | "cheque";
export type MatchReasonCode =
  | "PRICE_VARIANCE"
  | "QUANTITY_EXCEEDS_RECEIVED"
  | "QUANTITY_EXCEEDS_ORDERED"
  | "TOTAL_EXCEEDS_ORDER"
  | "DUPLICATE_INVOICE"
  | "UNKNOWN_LINE";

export interface ExceptionReason {
  code: MatchReasonCode;
  message: string;
  /** 1-based position of the invoice line the reason is about, when it is about one. */
  line: number | null;
  /** The other invoice, for a duplicate. */
  duplicate_of: number | null;
}

export interface InvoiceLine {
  id: number;
  po_item_id: number | null;
  product_id: number | null;
  description: string;
  quantity: number;
  unit_price: string;
  tax_rate_id: number | null;
  tax_name: string | null;
  tax_percent: string;
  tax_inclusive: boolean;
  reverse_charge: boolean;
  line_net: string;
  line_tax: string;
  line_total: string;
}

export interface InvoiceSummary {
  id: number;
  supplier: { id: number; name: string };
  purchase_order: { id: number; po_number: string };
  invoice_number: string;
  invoice_date: string;
  due_date: string;
  currency_code: string;
  subtotal: string;
  tax_total: string;
  grand_total: string;
  paid_total: string;
  open_amount: string;
  status: InvoiceStatus;
  match_mode: InvoiceMatchMode | null;
  tolerance_percent: string | null;
  exception_reasons: ExceptionReason[];
  notes: string | null;
  created_by: number;
  creator: Person;
  submitted_at: string | null;
  approved_by: number | null;
  approver: Person | null;
  approved_at: string | null;
  hold_reason: string | null;
  void_reason: string | null;
  rejection_reason: string | null;
  exchange_rate: string | null;
  base_subtotal: string | null;
  base_tax_total: string | null;
  base_grand_total: string | null;
  created_at: string;
  updated_at: string;
}

export interface Invoice extends InvoiceSummary {
  lines: InvoiceLine[];
}

export interface InvoiceListTotals {
  by_status: Partial<Record<InvoiceStatus, number>>;
  needing_attention: number;
  payables_outstanding: string;
  payables_overdue: string;
}

export interface InvoiceListResponse extends PaginatedResponse<InvoiceSummary> {
  totals: InvoiceListTotals;
}

export interface InvoiceListParams {
  page: number;
  page_size: number;
  status?: InvoiceStatus;
  supplier_id?: number;
  po_id?: number;
  due_before?: string;
  search?: string;
}

export interface InvoicePayment {
  id: number;
  invoice_id: number;
  payment_run_id: number | null;
  amount: string;
  currency_code: string;
  method: PaymentMethod;
  paid_on: string;
  reference: string | null;
  created_by: number;
  creator: Person;
  created_at: string;
}

export interface PaymentInput {
  amount: string;
  method: PaymentMethod;
  paid_on?: string | null;
  reference?: string | null;
}

const KEY = ["supplier-invoices"] as const;

export function useInvoices(params: InvoiceListParams) {
  return useQuery({
    queryKey: [...KEY, "list", params],
    queryFn: async () => {
      const { data } = await apiClient.get<InvoiceListResponse>("/supplier-invoices", { params });
      return data;
    },
  });
}

export function useInvoice(id: number | undefined) {
  return useQuery({
    queryKey: [...KEY, "detail", id],
    queryFn: async () => {
      const { data } = await apiClient.get<Invoice>(`/supplier-invoices/${id}`);
      return data;
    },
    enabled: id !== undefined,
  });
}

export function useInvoicePayments(id: number | undefined) {
  return useQuery({
    queryKey: [...KEY, "payments", id],
    queryFn: async () => {
      const { data } = await apiClient.get<InvoicePayment[]>(`/supplier-invoices/${id}/payments`);
      return data;
    },
    enabled: id !== undefined,
  });
}

function useInvalidateInvoices() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: KEY }),
      queryClient.invalidateQueries({ queryKey: ["approvals"] }),
      queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
    ]);
}

/** submit (match against the order), release: no body. */
export function useInvoiceTransition(action: "submit" | "release") {
  const invalidate = useInvalidateInvoices();
  return useMutation({
    mutationFn: async (id: number) => {
      const { data } = await apiClient.post<Invoice>(`/supplier-invoices/${id}/${action}`);
      return data;
    },
    onSuccess: invalidate,
  });
}

/** Approves a matched invoice, or decides the current approval step of an exception. The comment is optional. */
export function useApproveInvoice() {
  const invalidate = useInvalidateInvoices();
  return useMutation({
    mutationFn: async ({ id, comment }: { id: number; comment?: string }) => {
      const { data } = await apiClient.post<Invoice>(`/supplier-invoices/${id}/approve`, comment ? { comment } : {});
      return data;
    },
    onSuccess: invalidate,
  });
}

/** Sends the invoice back to draft; a comment is required. */
export function useRejectInvoice() {
  const invalidate = useInvalidateInvoices();
  return useMutation({
    mutationFn: async ({ id, comment }: { id: number; comment: string }) => {
      const { data } = await apiClient.post<Invoice>(`/supplier-invoices/${id}/reject`, { comment });
      return data;
    },
    onSuccess: invalidate,
  });
}

/** hold and void both need a reason. */
export function useInvoiceReasonAction(action: "hold" | "void") {
  const invalidate = useInvalidateInvoices();
  return useMutation({
    mutationFn: async ({ id, reason }: { id: number; reason: string }) => {
      const { data } = await apiClient.post<Invoice>(`/supplier-invoices/${id}/${action}`, { reason });
      return data;
    },
    onSuccess: invalidate,
  });
}

export function useRecordPayment(invoiceId: number) {
  const invalidate = useInvalidateInvoices();
  return useMutation({
    mutationFn: async (input: PaymentInput) => {
      const { data } = await apiClient.post<InvoicePayment>(`/supplier-invoices/${invoiceId}/payments`, input);
      return data;
    },
    onSuccess: invalidate,
  });
}
