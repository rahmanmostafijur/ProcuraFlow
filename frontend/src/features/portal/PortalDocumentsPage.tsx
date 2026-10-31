import { extractErrorMessage } from "@/api/client";
import {
  downloadPortalDocument,
  useDeletePortalDocument,
  usePortalDocuments,
  useUploadPortalDocument,
} from "@/api/portal";
import type { DocumentUploadInput, SupplierDocument } from "@/api/supplierDocuments";
import { DocumentsTable } from "@/components/documents/DocumentsTable";
import { DocumentUploadForm } from "@/components/documents/DocumentUploadForm";
import { Card } from "@/components/ui/Card";
import { useToast } from "@/components/ui/toast-context";

export function PortalDocumentsPage() {
  const { showToast } = useToast();
  const { data: documents, isLoading, isError } = usePortalDocuments();
  const upload = useUploadPortalDocument();
  const remove = useDeletePortalDocument();

  const handleUpload = async (input: DocumentUploadInput) => {
    try {
      await upload.mutateAsync(input);
      showToast("Document uploaded");
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
      throw error;
    }
  };

  const handleDelete = async (doc: SupplierDocument) => {
    try {
      await remove.mutateAsync(doc.id);
      showToast("Document deleted");
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  const handleDownload = async (doc: SupplierDocument) => {
    try {
      await downloadPortalDocument(doc);
    } catch {
      showToast("The document could not be downloaded. Please try again.", "error");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Your documents</h1>
        <p className="text-sm text-slate-500">Keep certificates and tax forms current so payments are not held up.</p>
      </div>
      <Card className="space-y-4 p-6">
        {isLoading && <p className="text-sm text-slate-500">Loading documents…</p>}
        {isError && <p className="text-sm text-red-600">The documents could not be loaded.</p>}
        {documents && (
          <DocumentsTable
            documents={documents}
            disabled={remove.isPending}
            onDownload={(doc) => void handleDownload(doc)}
            onDelete={(doc) => void handleDelete(doc)}
          />
        )}
        <DocumentUploadForm isPending={upload.isPending} onSubmit={handleUpload} />
      </Card>
    </div>
  );
}
