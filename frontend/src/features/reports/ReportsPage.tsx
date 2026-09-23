import { Download } from "lucide-react";

import type { DelayedDelivery, SupplierPerformance } from "@/api/types";
import { useDelayedDeliveries, useOnTimeDeliveryRate, useSupplierPerformance } from "@/api/reports";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { LoadingState } from "@/components/ui/LoadingState";
import { formatCurrency, formatDate } from "@/lib/utils";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

export function ReportsPage() {
  const { data: performance, isLoading: performanceLoading } = useSupplierPerformance();
  const { data: delayed, isLoading: delayedLoading } = useDelayedDeliveries();
  const { data: onTimeRate } = useOnTimeDeliveryRate();

  const performanceColumns: Column<SupplierPerformance>[] = [
    { header: "Supplier", accessor: (row) => row.supplier_name },
    { header: "Orders", accessor: (row) => row.order_count },
    { header: "Total Spend", accessor: (row) => formatCurrency(row.total_spend) },
  ];

  const delayedColumns: Column<DelayedDelivery>[] = [
    { header: "PO Number", accessor: (row) => row.po_number },
    { header: "Supplier", accessor: (row) => row.supplier_name },
    { header: "Expected", accessor: (row) => formatDate(row.expected_date) },
    { header: "Actual", accessor: (row) => formatDate(row.actual_date) },
    { header: "Variance (days)", accessor: (row) => row.variance_days ?? "—" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Reports</h1>
          <p className="text-sm text-slate-500">Purchasing, supplier, and inventory analytics.</p>
        </div>
        <a href={`${API_BASE_URL}/reports/inventory-status.csv`} target="_blank" rel="noreferrer">
          <Button variant="secondary">
            <Download className="h-4 w-4" /> Export Inventory CSV
          </Button>
        </a>
      </div>

      <Card className="p-5">
        <h2 className="mb-1 text-sm font-semibold text-slate-900">On-Time Delivery Rate</h2>
        <p className="text-3xl font-semibold text-brand-600">
          {onTimeRate ? `${onTimeRate.on_time_percentage}%` : "—"}
        </p>
        <p className="text-xs text-slate-500">Calculated from all completed deliveries.</p>
      </Card>

      <Card>
        <div className="border-b border-slate-200 px-5 py-4">
          <h2 className="text-sm font-semibold text-slate-900">Supplier Performance</h2>
        </div>
        {performanceLoading ? (
          <LoadingState />
        ) : (
          <DataTable
            columns={performanceColumns}
            rows={performance ?? []}
            keyExtractor={(row) => row.supplier_id}
            emptyTitle="No supplier activity yet"
          />
        )}
      </Card>

      <Card>
        <div className="border-b border-slate-200 px-5 py-4">
          <h2 className="text-sm font-semibold text-slate-900">Delayed Deliveries</h2>
        </div>
        {delayedLoading ? (
          <LoadingState />
        ) : (
          <DataTable
            columns={delayedColumns}
            rows={delayed ?? []}
            keyExtractor={(row) => row.po_number}
            emptyTitle="No delayed deliveries"
            emptyDescription="Great! All deliveries have arrived on time so far."
          />
        )}
      </Card>
    </div>
  );
}
