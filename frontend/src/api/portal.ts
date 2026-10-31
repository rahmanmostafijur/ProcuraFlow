import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "./client";
import { downloadFile } from "./downloads";
import { documentForm, type DocumentUploadInput, type SupplierDocument } from "./supplierDocuments";
import type { Attachment, PaginatedResponse, POStatus } from "./types";

export interface PortalMe {
  id: number;
  email: string;
  full_name: string;
  supplier: { id: number; name: string };
}

export interface PortalOrderLine {
  product_id: number;
  product_name: string;
  sku: string;
  quantity: number;
  received_quantity: number;
  unit_price: string;
  tax_name: string | null;
  tax_percent: string;
  line_total: string;
}

export interface PortalOrderSummary {
  id: number;
  po_number: string;
  status: POStatus;
  currency_code: string;
  subtotal: string;
  tax_total: string;
  grand_total: string;
  expected_delivery_date: string | null;
  version: number;
  created_at: string;
  acknowledged_at: string | null;
}

export interface PortalOrder extends PortalOrderSummary {
  items: PortalOrderLine[];
}

export interface PortalInvoice {
  id: number;
  invoice_number: string;
  po_id: number;
  po_number: string;
  invoice_date: string;
  due_date: string;
  currency_code: string;
  subtotal: string;
  tax_total: string;
  grand_total: string;
  paid_total: string;
  open_amount: string;
  status: string;
  created_at: string;
}

export interface PortalInvoiceInput {
  po_id: number;
  invoice_number: string;
  invoice_date: string;
  due_date?: string;
  notes?: string;
  lines: { product_id: number; quantity: number; unit_price: string }[];
}

export function usePortalMe() {
  return useQuery({
    queryKey: ["portal", "me"],
    queryFn: async () => (await apiClient.get<PortalMe>("/portal/me")).data,
  });
}

export function usePortalOrders(page: number, pageSize: number) {
  return useQuery({
    queryKey: ["portal", "orders", page, pageSize],
    queryFn: async () =>
      (
        await apiClient.get<PaginatedResponse<PortalOrderSummary>>("/portal/orders", {
          params: { page, page_size: pageSize },
        })
      ).data,
  });
}

export function usePortalOrder(id: number | null) {
  return useQuery({
    queryKey: ["portal", "order", id],
    enabled: id !== null,
    queryFn: async () => (await apiClient.get<PortalOrder>(`/portal/orders/${id}`)).data,
  });
}

export function useAcknowledgeOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => (await apiClient.post<PortalOrder>(`/portal/orders/${id}/acknowledge`)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["portal"] }),
  });
}

export function usePortalInvoices(page: number, pageSize: number) {
  return useQuery({
    queryKey: ["portal", "invoices", page, pageSize],
    queryFn: async () =>
      (
        await apiClient.get<PaginatedResponse<PortalInvoice>>("/portal/invoices", {
          params: { page, page_size: pageSize },
        })
      ).data,
  });
}

/** Creates the draft invoice, then attaches its PDF or photo; the invoice exists even if the file is refused. */
export function useCreatePortalInvoice() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ input, file }: { input: PortalInvoiceInput; file: File }) => {
      const { data: invoice } = await apiClient.post<PortalInvoice>("/portal/invoices", input);
      const form = new FormData();
      form.append("file", file);
      await apiClient.post(`/portal/invoices/${invoice.id}/files`, form);
      return invoice;
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["portal", "invoices"] }),
  });
}

export function usePortalInvoiceFiles(invoiceId: number | null) {
  return useQuery({
    queryKey: ["portal", "invoice-files", invoiceId],
    enabled: invoiceId !== null,
    queryFn: async () => (await apiClient.get<Attachment[]>(`/portal/invoices/${invoiceId}/files`)).data,
  });
}

export function useUploadPortalInvoiceFile(invoiceId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return (await apiClient.post<Attachment>(`/portal/invoices/${invoiceId}/files`, form)).data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["portal", "invoice-files", invoiceId] }),
  });
}

export function downloadPortalInvoiceFile(invoiceId: number, file: Attachment): Promise<void> {
  return downloadFile(`/portal/invoices/${invoiceId}/files/${file.id}/download`, file.filename);
}

export function usePortalDocuments() {
  return useQuery({
    queryKey: ["portal", "documents"],
    queryFn: async () => (await apiClient.get<SupplierDocument[]>("/portal/documents")).data,
  });
}

export function useUploadPortalDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: DocumentUploadInput) =>
      (await apiClient.post<SupplierDocument>("/portal/documents", documentForm(input))).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["portal", "documents"] }),
  });
}

export function useDeletePortalDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await apiClient.delete(`/portal/documents/${id}`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["portal", "documents"] }),
  });
}

export function downloadPortalDocument(doc: SupplierDocument): Promise<void> {
  return downloadFile(`/portal/documents/${doc.id}/download`, doc.filename);
}
