import { useState } from "react";

import { useAuditLogs } from "@/api/audit";
import type { AuditLog } from "@/api/types";
import { Card } from "@/components/ui/Card";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Pagination } from "@/components/ui/Pagination";
import { formatDateTime } from "@/lib/utils";

const PAGE_SIZE = 20;

export function AuditLogPage() {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useAuditLogs(page, PAGE_SIZE);

  const columns: Column<AuditLog>[] = [
    { header: "Date", accessor: (row) => formatDateTime(row.created_at) },
    { header: "Action", accessor: (row) => <span className="font-medium">{row.action.replace(/_/g, " ")}</span> },
    { header: "Entity", accessor: (row) => `${row.entity_type}${row.entity_id ? ` #${row.entity_id}` : ""}` },
    { header: "User ID", accessor: (row) => row.user_id ?? "System" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Audit Log</h1>
        <p className="text-sm text-slate-500">A record of every significant action taken in the system.</p>
      </div>

      <Card>
        <DataTable
          columns={columns}
          rows={data?.items ?? []}
          keyExtractor={(row) => row.id}
          isLoading={isLoading}
          emptyTitle="No audit events yet"
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
    </div>
  );
}
