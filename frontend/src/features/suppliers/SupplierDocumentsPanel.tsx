import { extractErrorMessage } from "@/api/client";
import {
  downloadSupplierDocument,
  useDeleteSupplierDocument,
  useSupplierDocuments,
  useUploadSupplierDocument,
  type DocumentUploadInput,
  type SupplierDocument,
} from "@/api/supplierDocuments";
import { DocumentsTable } from "@/components/documents/DocumentsTable";
import { DocumentUploadForm } from "@/components/documents/DocumentUploadForm";
import { Card } from "@/components/ui/Card";
import { useToast } from "@/components/ui/toast-context";

export function SupplierDocumentsPanel({ supplierId }: { supplierId: number }) {
  const { showToast } = useToast();
  const { data: documents, isLoading, isError } = useSupplierDocuments(supplierId);
  const upload = useUploadSupplierDocument(supplierId);
  const remove = useDeleteSupplierDocument(supplierId);

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
      await downloadSupplierDocument(supplierId, doc);
    } catch {
      showToast("The document could not be downloaded. Please try again.", "error");
    }
  };

  return (
    <Card className="space-y-4 p-6">
      <div>
        <h2 className="text-base font-semibold text-text-primary">Documents</h2>
        <p className="text-sm text-text-secondary">W-9, VAT certificate, insurance, ISO certificate and bank letter.</p>
      </div>
      {isLoading && <p className="text-sm text-text-secondary">Loading documents…</p>}
      {isError && <p className="text-sm text-danger-fg">The documents could not be loaded.</p>}
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
  );
}
