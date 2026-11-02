import { Link } from "react-router-dom";

import {
  DOCUMENT_STATUS_LABELS,
  DOCUMENT_TYPE_LABELS,
  useExpiringDocuments,
  type ExpiringDocument,
} from "@/api/supplierDocuments";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Card } from "@/components/ui/Card";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { PageHeader } from "@/components/ui/PageHeader";
import { formatDate } from "@/lib/utils";

export function ExpiringDocumentsPage() {
  const { data, isLoading } = useExpiringDocuments();

  const columns: Column<ExpiringDocument>[] = [
    {
      header: "Supplier",
      accessor: (row) => (
        <Link to={`/suppliers/${row.supplier_id}`} className="font-medium text-brand hover:underline">
          {row.supplier_name}
        </Link>
      ),
    },
    { header: "Document", accessor: (row) => DOCUMENT_TYPE_LABELS[row.document_type] },
    { header: "Expires", accessor: (row) => (row.expiry_date ? formatDate(row.expiry_date) : "—") },
    {
      header: "Status",
      accessor: (row) => <StatusBadge status={row.status} label={DOCUMENT_STATUS_LABELS[row.status]} />,
    },
  ];

  return (
    <div>
      <PageHeader
        title="Documents expiring soon"
        description="Documents of active suppliers that expire within 30 days or already have."
        breadcrumbs={[{ label: "Suppliers", to: "/suppliers" }, { label: "Documents expiring soon" }]}
      />
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
