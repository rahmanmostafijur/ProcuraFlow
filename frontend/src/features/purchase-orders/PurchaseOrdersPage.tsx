import { Plus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { extractErrorMessage } from "@/api/client";
import { useCreatePurchaseOrder, usePurchaseOrders, type PurchaseOrderInput } from "@/api/purchaseOrders";
import type { POStatus, PurchaseOrder } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Pagination } from "@/components/ui/Pagination";
import { Select } from "@/components/ui/Select";
import { useToast } from "@/components/ui/toast-context";
import { useAuth } from "@/lib/auth-context";
import { formatCurrency, formatDate } from "@/lib/utils";

import { PurchaseOrderFormModal } from "./PurchaseOrderFormModal";

const PAGE_SIZE = 10;

const STATUS_OPTIONS: { value: POStatus | ""; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "draft", label: "Draft" },
  { value: "submitted", label: "Submitted" },
  { value: "approved", label: "Approved" },
  { value: "ordered", label: "Ordered" },
  { value: "partially_received", label: "Partially Received" },
  { value: "received", label: "Received" },
  { value: "cancelled", label: "Cancelled" },
];

export function PurchaseOrdersPage() {
  const { hasPermission } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<POStatus | "">("");
  const [isModalOpen, setModalOpen] = useState(false);

  const { data, isLoading } = usePurchaseOrders({ page, page_size: PAGE_SIZE, status: status || undefined });
  const createPO = useCreatePurchaseOrder();

  const canCreate = hasPermission("po:create");

  const columns: Column<PurchaseOrder>[] = [
    { header: "PO Number", accessor: (row) => <span className="font-medium text-slate-900">{row.po_number}</span> },
    { header: "Supplier", accessor: (row) => row.supplier.name },
    { header: "Status", accessor: (row) => <Badge status={row.status}>{row.status.replace(/_/g, " ")}</Badge> },
    { header: "Total", accessor: (row) => formatCurrency(row.total) },
    { header: "Expected Delivery", accessor: (row) => formatDate(row.expected_delivery_date) },
    { header: "Created", accessor: (row) => formatDate(row.created_at) },
  ];

  const handleCreate = async (values: PurchaseOrderInput) => {
    try {
      const po = await createPO.mutateAsync(values);
      showToast("Purchase order created");
      setModalOpen(false);
      navigate(`/purchase-orders/${po.id}`);
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Purchase Orders</h1>
          <p className="text-sm text-slate-500">Track orders from draft through delivery.</p>
        </div>
        {canCreate && (
          <Button onClick={() => setModalOpen(true)}>
            <Plus className="h-4 w-4" /> New Purchase Order
          </Button>
        )}
      </div>

      <Card>
        <div className="border-b border-slate-200 p-4">
          <Select
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as POStatus | "");
              setPage(1);
            }}
            className="max-w-xs"
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </div>
        <DataTable
          columns={columns}
          rows={data?.items ?? []}
          keyExtractor={(row) => row.id}
          isLoading={isLoading}
          emptyTitle="No purchase orders found"
          emptyDescription="Create a purchase order to get started."
          onRowClick={(row) => navigate(`/purchase-orders/${row.id}`)}
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

      <PurchaseOrderFormModal
        isOpen={isModalOpen}
        onClose={() => setModalOpen(false)}
        onSubmit={handleCreate}
        isSubmitting={createPO.isPending}
      />
    </div>
  );
}
