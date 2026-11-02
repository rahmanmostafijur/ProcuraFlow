import { Download } from "lucide-react";
import { useState } from "react";

import { extractErrorMessage } from "@/api/client";
import type { DelayedDelivery, SupplierPerformance } from "@/api/types";
import {
  downloadInventoryStatusCsv,
  useDelayedDeliveries,
  useOnTimeDeliveryRate,
  useSupplierPerformance,
} from "@/api/reports";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { LoadingState } from "@/components/ui/LoadingState";
import { PageHeader } from "@/components/ui/PageHeader";
import { useToast } from "@/components/ui/toast-context";
import { formatCurrency, formatDate } from "@/lib/utils";

export function ReportsPage() {
  const { showToast } = useToast();
  const [isExporting, setIsExporting] = useState(false);
  const { data: performance, isLoading: performanceLoading } = useSupplierPerformance();
  const { data: delayed, isLoading: delayedLoading } = useDelayedDeliveries();
  const { data: onTimeRate } = useOnTimeDeliveryRate();

  const exportInventoryCsv = async () => {
    setIsExporting(true);
    try {
      await downloadInventoryStatusCsv();
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    } finally {
      setIsExporting(false);
    }
  };

  const performanceColumns: Column<SupplierPerformance>[] = [
    { header: "Supplier", accessor: (row) => row.supplier_name },
    { header: "Committed Orders", accessor: (row) => row.order_count, isAmount: true },
    { header: "Committed Spend", accessor: (row) => formatCurrency(row.total_spend), isAmount: true },
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
      <PageHeader
        title="Reports"
        description="Purchasing, supplier, and inventory analytics."
        primaryAction={
          <Button variant="secondary" onClick={() => void exportInventoryCsv()} disabled={isExporting}>
            <Download className="h-4 w-4" /> {isExporting ? "Exporting…" : "Export Inventory CSV"}
          </Button>
        }
      />

      <Card padding="lg">
        <h2 className="mb-1 text-sm font-semibold text-text-primary">On-Time Delivery Rate</h2>
        <p className="text-3xl font-semibold tabular-nums text-brand">
          {onTimeRate ? `${onTimeRate.on_time_percentage}%` : "—"}
        </p>
        <p className="text-xs text-text-secondary">Calculated from all completed deliveries.</p>
      </Card>

      <Card>
        <div className="border-b border-border px-5 py-4">
          <h2 className="text-sm font-semibold text-text-primary">Supplier Performance</h2>
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
        <div className="border-b border-border px-5 py-4">
          <h2 className="text-sm font-semibold text-text-primary">Delayed Deliveries</h2>
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
