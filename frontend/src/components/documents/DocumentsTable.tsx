import { Download, Trash2 } from "lucide-react";

import { DOCUMENT_STATUS_LABELS, DOCUMENT_TYPE_LABELS, type SupplierDocument } from "@/api/supplierDocuments";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { formatDate } from "@/lib/utils";

interface DocumentsTableProps {
  documents: SupplierDocument[];
  onDownload: (doc: SupplierDocument) => void;
  onDelete: (doc: SupplierDocument) => void;
  disabled?: boolean;
}

/** The status badge shows what the server computed from the expiry date; it is never worked out here. */
export function DocumentsTable({ documents, onDownload, onDelete, disabled }: DocumentsTableProps) {
  if (documents.length === 0) return <p className="text-sm text-text-secondary">No documents on file.</p>;
  return (
    <table className="w-full text-left text-sm">
      <thead className="text-xs uppercase text-text-secondary">
        <tr>
          <th className="py-2 pr-3">Type</th>
          <th className="py-2 pr-3">File</th>
          <th className="py-2 pr-3">Expires</th>
          <th className="py-2 pr-3">Status</th>
          <th className="py-2 text-right">
            <span className="sr-only">Actions</span>
          </th>
        </tr>
      </thead>
      <tbody className="divide-y divide-border">
        {documents.map((doc) => (
          <tr key={doc.id}>
            <td className="py-2 pr-3 font-medium text-text-primary">{DOCUMENT_TYPE_LABELS[doc.document_type]}</td>
            <td className="py-2 pr-3 text-text-secondary">{doc.filename}</td>
            <td className="py-2 pr-3 text-text-secondary">
              {doc.expiry_date ? formatDate(doc.expiry_date) : "No expiry"}
            </td>
            <td className="py-2 pr-3">
              <StatusBadge status={doc.status} label={DOCUMENT_STATUS_LABELS[doc.status]} />
            </td>
            <td className="py-2 text-right">
              <Button variant="ghost" size="sm" aria-label={`Download ${doc.filename}`} onClick={() => onDownload(doc)}>
                <Download className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                aria-label={`Delete ${doc.filename}`}
                disabled={disabled}
                onClick={() => onDelete(doc)}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
