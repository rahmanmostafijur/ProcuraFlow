import { useState } from "react";

import { useDeliveries } from "@/api/deliveries";
import type { Delivery } from "@/api/types";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Card } from "@/components/ui/Card";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { formatDate } from "@/lib/utils";

const PAGE_SIZE = 15;

export function DeliveriesPage() {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useDeliveries(page, PAGE_SIZE);

  const columns: Column<Delivery>[] = [
    { header: "PO ID", accessor: (row) => row.po_id },
    { header: "Status", accessor: (row) => <StatusBadge status={row.status} label={row.status.replace(/_/g, " ")} /> },
    { header: "Expected Date", accessor: (row) => formatDate(row.expected_date) },
    { header: "Actual Date", accessor: (row) => formatDate(row.actual_date) },
    { header: "Ordered Qty", accessor: (row) => row.ordered_quantity },
    { header: "Received Qty", accessor: (row) => row.received_quantity },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Deliveries" description="Track expected vs. actual delivery performance." />

      <Card>
        <DataTable
          columns={columns}
          rows={data?.items ?? []}
          keyExtractor={(row) => row.id}
          isLoading={isLoading}
          emptyTitle="No deliveries yet"
          emptyDescription="Deliveries are created automatically when a purchase order is marked as ordered."
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
