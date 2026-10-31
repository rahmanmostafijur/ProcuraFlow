import { useState } from "react";

import { usePaymentRuns, type PaymentRun } from "@/api/paymentRuns";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Pagination } from "@/components/ui/Pagination";
import { formatCurrency, formatDate } from "@/lib/utils";

import { PaymentRunModal } from "./PaymentRunModal";

const PAGE_SIZE = 10;

export function PaymentRunsPage() {
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const { data, isLoading } = usePaymentRuns(page, PAGE_SIZE);
  // Looked up from the list so the open dialog shows fresh data after a release.
  const selected = data?.items.find((run) => run.id === selectedId) ?? null;

  const columns: Column<PaymentRun>[] = [
    { header: "Run", accessor: (row) => <span className="font-medium text-slate-900">{row.number}</span> },
    { header: "Status", accessor: (row) => <Badge status={row.status}>{row.status}</Badge> },
    { header: "Payments", accessor: (row) => row.items.length },
    { header: "Total", accessor: (row) => formatCurrency(row.total, row.currency_code) },
    { header: "Created", accessor: (row) => formatDate(row.created_at) },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Payment runs</h1>
        <p className="text-sm text-slate-500">Open a released run to generate or download its bank file.</p>
      </div>
      <Card>
        <DataTable
          columns={columns}
          rows={data?.items ?? []}
          keyExtractor={(row) => row.id}
          isLoading={isLoading}
          emptyTitle="No payment runs"
          emptyDescription="Runs appear here once approved invoices are grouped for payment."
          onRowClick={(row) => setSelectedId(row.id)}
        />
        {data && (
          <Pagination
            page={data.page}
            totalPages={data.total_pages}
            total={data.total}
            pageSize={data.page_size}
            onPageChange={setPage}
          />
        )}
      </Card>
      <PaymentRunModal run={selected} onClose={() => setSelectedId(null)} />
    </div>
  );
}
