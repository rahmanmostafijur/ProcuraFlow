import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "./client";
import { downloadFile } from "./downloads";

export type SupplierDocumentType = "w9" | "vat_certificate" | "insurance" | "iso_certificate" | "bank_letter";
/** Worked out by the server from the expiry date; never edited or stored here. */
export type SupplierDocumentStatus = "valid" | "expiring_soon" | "expired";

export const DOCUMENT_TYPE_LABELS: Record<SupplierDocumentType, string> = {
  w9: "W-9",
  vat_certificate: "VAT certificate",
  insurance: "Insurance",
  iso_certificate: "ISO certificate",
  bank_letter: "Bank letter",
};

export const DOCUMENT_STATUS_LABELS: Record<SupplierDocumentStatus, string> = {
  valid: "Valid",
  expiring_soon: "Expiring soon",
  expired: "Expired",
};

export interface SupplierDocument {
  id: number;
  supplier_id: number;
  document_type: SupplierDocumentType;
  issue_date: string | null;
  expiry_date: string | null;
  status: SupplierDocumentStatus;
  days_until_expiry: number | null;
  filename: string;
  content_type: string;
  size_bytes: number;
  uploaded_by: { id: number; full_name: string };
  created_at: string;
}

export interface ExpiringDocument extends SupplierDocument {
  supplier_name: string;
}

export interface DocumentUploadInput {
  file: File;
  document_type: SupplierDocumentType;
  issue_date?: string;
  expiry_date?: string;
}

export function documentForm(input: DocumentUploadInput): FormData {
  const form = new FormData();
  form.append("file", input.file);
  form.append("document_type", input.document_type);
  if (input.issue_date) form.append("issue_date", input.issue_date);
  if (input.expiry_date) form.append("expiry_date", input.expiry_date);
  return form;
}

const key = (supplierId: number) => ["supplier-documents", supplierId] as const;

export function useSupplierDocuments(supplierId: number) {
  return useQuery({
    queryKey: key(supplierId),
    queryFn: async () => {
      const { data } = await apiClient.get<SupplierDocument[]>(`/suppliers/${supplierId}/documents`);
      return data;
    },
  });
}

export function useUploadSupplierDocument(supplierId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: DocumentUploadInput) => {
      const { data } = await apiClient.post<SupplierDocument>(
        `/suppliers/${supplierId}/documents`,
        documentForm(input),
      );
      return data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["supplier-documents"] });
    },
  });
}

export function useDeleteSupplierDocument(supplierId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (documentId: number) => {
      await apiClient.delete(`/suppliers/${supplierId}/documents/${documentId}`);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["supplier-documents"] });
    },
  });
}

export function downloadSupplierDocument(supplierId: number, doc: SupplierDocument): Promise<void> {
  return downloadFile(`/suppliers/${supplierId}/documents/${doc.id}/download`, doc.filename);
}

export function useExpiringDocuments() {
  return useQuery({
    queryKey: ["supplier-documents", "expiring"],
    queryFn: async () => {
      const { data } = await apiClient.get<ExpiringDocument[]>("/supplier-documents/expiring");
      return data;
    },
  });
}
