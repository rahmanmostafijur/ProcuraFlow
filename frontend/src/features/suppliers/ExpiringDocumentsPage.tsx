import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";

import {
  DOCUMENT_STATUS_LABELS,
  DOCUMENT_TYPE_LABELS,
  useExpiringDocuments,
  type ExpiringDocument,
} from "@/api/supplierDocuments";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { formatDate } from "@/lib/utils";

export function ExpiringDocumentsPage() {
  const { data, isLoading } = useExpiringDocuments();

  const columns: Column<ExpiringDocument>[] = [
    {
      header: "Supplier",
      accessor: (row) => (
        <Link to={`/suppliers/${row.supplier_id}`} className="font-medium text-brand-700 hover:underline">
          {row.supplier_name}
        </Link>
      ),
    },
    { header: "Document", accessor: (row) => DOCUMENT_TYPE_LABELS[row.document_type] },
    { header: "Expires", accessor: (row) => (row.expiry_date ? formatDate(row.expiry_date) : "—") },
    { header: "Status", accessor: (row) => <Badge status={row.status}>{DOCUMENT_STATUS_LABELS[row.status]}</Badge> },
  ];

  return (
    <div className="space-y-6">
      <div>
        <Link
          to="/suppliers"
          className="mb-2 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800"
        >
          <ArrowLeft className="h-4 w-4" /> Suppliers
        </Link>
        <h1 className="text-2xl font-semibold text-slate-900">Documents expiring soon</h1>
        <p className="text-sm text-slate-500">
          Documents of active suppliers that expire within 30 days or already have.
        </p>
      </div>
      <Card>
        <DataTable
          columns={columns}
          rows={data ?? []}
          keyExtractor={(row) => row.id}
          isLoading={isLoading}
          emptyTitle="Nothing is expiring"
          emptyDescription="Every supplier document is valid for now."
        />
      </Card>
    </div>
  );
}
