import { useState } from "react";

import { usePortalOrders, type PortalOrderSummary } from "@/api/portal";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Card } from "@/components/ui/Card";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Pagination } from "@/components/ui/Pagination";
import { PageHeader } from "@/components/ui/PageHeader";
import { formatCurrency, formatDate } from "@/lib/utils";

import { PortalOrderModal } from "./PortalOrderModal";

const PAGE_SIZE = 10;

export function PortalOrdersPage() {
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState<number | null>(null);
  const { data, isLoading } = usePortalOrders(page, PAGE_SIZE);

  const columns: Column<PortalOrderSummary>[] = [
    { header: "Order", accessor: (row) => <span className="font-medium text-text-primary">{row.po_number}</span> },
    { header: "Status", accessor: (row) => <StatusBadge status={row.status} /> },
    { header: "Total", accessor: (row) => formatCurrency(row.grand_total, row.currency_code) },
    {
      header: "Delivery",
      accessor: (row) => (row.expected_delivery_date ? formatDate(row.expected_delivery_date) : "—"),
    },
    {
      header: "Acknowledged",
      accessor: (row) =>
        row.acknowledged_at ? formatDate(row.acknowledged_at) : <StatusBadge status="pending" label="Waiting" />,
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Your orders" description="Open an order to see its lines and confirm that you received it." />
      <Card>
        <DataTable
          columns={columns}
          rows={data?.items ?? []}
          keyExtractor={(row) => row.id}
          isLoading={isLoading}
          emptyTitle="No orders yet"
          emptyDescription="Orders appear here once they are placed with you."
          onRowClick={(row) => setOpenId(row.id)}
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
      <PortalOrderModal orderId={openId} onClose={() => setOpenId(null)} />
    </div>
  );
}
