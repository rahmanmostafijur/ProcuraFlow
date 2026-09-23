import { Plus } from "lucide-react";
import { useState } from "react";

import { extractErrorMessage } from "@/api/client";
import { useCreateInventoryAdjustment, useInventoryTransactions } from "@/api/inventory";
import type { InventoryTransaction } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Pagination } from "@/components/ui/Pagination";
import { useToast } from "@/components/ui/toast-context";
import { useAuth } from "@/lib/auth-context";
import { formatDateTime } from "@/lib/utils";

import { InventoryAdjustmentModal } from "./InventoryAdjustmentModal";

const PAGE_SIZE = 15;

export function InventoryPage() {
  const { hasPermission } = useAuth();
  const { showToast } = useToast();
  const [page, setPage] = useState(1);
  const [isModalOpen, setModalOpen] = useState(false);

  const { data, isLoading } = useInventoryTransactions({ page, page_size: PAGE_SIZE });
  const createAdjustment = useCreateInventoryAdjustment();

  const canWrite = hasPermission("inventory:write");

  const columns: Column<InventoryTransaction>[] = [
    { header: "Date", accessor: (row) => formatDateTime(row.created_at) },
    { header: "Product ID", accessor: (row) => row.product_id },
    { header: "Type", accessor: (row) => <Badge>{row.type.replace(/_/g, " ")}</Badge> },
    {
      header: "Quantity",
      accessor: (row) => (
        <span className={row.quantity_delta >= 0 ? "text-green-700" : "text-red-700"}>
          {row.quantity_delta >= 0 ? "+" : ""}
          {row.quantity_delta}
        </span>
      ),
    },
    { header: "Resulting Stock", accessor: (row) => row.resulting_stock },
    { header: "Reason", accessor: (row) => row.reason ?? "—" },
  ];

  const handleSubmit = async (values: { product_id: number; quantity_delta: number; reason: string }) => {
    try {
      await createAdjustment.mutateAsync(values);
      showToast("Inventory adjusted");
      setModalOpen(false);
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Inventory</h1>
          <p className="text-sm text-slate-500">Full transaction history for every stock movement.</p>
        </div>
        {canWrite && (
          <Button onClick={() => setModalOpen(true)}>
            <Plus className="h-4 w-4" /> Adjust Stock
          </Button>
        )}
      </div>

      <Card>
        <DataTable
          columns={columns}
          rows={data?.items ?? []}
          keyExtractor={(row) => row.id}
          isLoading={isLoading}
          emptyTitle="No inventory transactions yet"
          emptyDescription="Stock movements from receiving and adjustments will appear here."
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

      <InventoryAdjustmentModal
        isOpen={isModalOpen}
        onClose={() => setModalOpen(false)}
        onSubmit={handleSubmit}
        isSubmitting={createAdjustment.isPending}
      />
    </div>
  );
}
