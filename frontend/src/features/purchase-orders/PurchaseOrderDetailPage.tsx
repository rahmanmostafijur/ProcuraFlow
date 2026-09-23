import { ArrowLeft } from "lucide-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { extractErrorMessage } from "@/api/client";
import {
  usePurchaseOrder,
  usePurchaseOrderTransition,
  useReceivePurchaseOrder,
} from "@/api/purchaseOrders";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingState";
import { useToast } from "@/components/ui/toast-context";
import { useAuth } from "@/lib/auth-context";
import { formatCurrency, formatDate, formatDateTime } from "@/lib/utils";

import { ReceivePurchaseOrderModal } from "./ReceivePurchaseOrderModal";

type PendingAction = "submit" | "approve" | "order" | "cancel" | null;

export function PurchaseOrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const { showToast } = useToast();
  const poId = id ? Number(id) : undefined;

  const { data: po, isLoading, isError } = usePurchaseOrder(poId);
  const submitMutation = usePurchaseOrderTransition("submit");
  const approveMutation = usePurchaseOrderTransition("approve");
  const orderMutation = usePurchaseOrderTransition("order");
  const cancelMutation = usePurchaseOrderTransition("cancel");
  const receiveMutation = useReceivePurchaseOrder();

  const [pendingAction, setPendingAction] = useState<PendingAction>(null);
  const [isReceiveModalOpen, setReceiveModalOpen] = useState(false);

  if (isLoading) return <LoadingState label="Loading purchase order…" />;
  if (isError || !po) return <ErrorState message="Purchase order not found." />;

  const mutationForAction = {
    submit: submitMutation,
    approve: approveMutation,
    order: orderMutation,
    cancel: cancelMutation,
  } as const;

  const runTransition = async (action: Exclude<PendingAction, null>) => {
    try {
      await mutationForAction[action].mutateAsync(po.id);
      const pastTense: Record<Exclude<PendingAction, null>, string> = {
        submit: "submitted",
        approve: "approved",
        order: "marked as ordered",
        cancel: "cancelled",
      };
      showToast(`Purchase order ${pastTense[action]}`);
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    } finally {
      setPendingAction(null);
    }
  };

  const handleReceive = async (items: { product_id: number; quantity: number }[]) => {
    try {
      await receiveMutation.mutateAsync({ id: po.id, items });
      showToast("Stock received");
      setReceiveModalOpen(false);
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  const canCreate = hasPermission("po:create");
  const canApprove = hasPermission("po:approve");
  const canTransition = hasPermission("po:transition");
  const canReceive = hasPermission("inventory:write");

  const actions: { label: string; action: Exclude<PendingAction, null>; visible: boolean; variant?: "primary" | "danger" }[] = [
    { label: "Submit for Approval", action: "submit", visible: po.status === "draft" && canCreate },
    { label: "Approve", action: "approve", visible: po.status === "submitted" && canApprove },
    { label: "Mark as Ordered", action: "order", visible: po.status === "approved" && canTransition },
    {
      label: "Cancel Order",
      action: "cancel",
      variant: "danger",
      visible: ["draft", "submitted", "approved", "ordered"].includes(po.status) && canTransition,
    },
  ];

  const canReceiveNow = ["ordered", "partially_received"].includes(po.status) && canReceive;

  return (
    <div className="space-y-6">
      <button
        onClick={() => navigate("/purchase-orders")}
        className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700"
      >
        <ArrowLeft className="h-4 w-4" /> Back to purchase orders
      </button>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold text-slate-900">{po.po_number}</h1>
            <Badge status={po.status}>{po.status.replace(/_/g, " ")}</Badge>
          </div>
          <p className="text-sm text-slate-500">Supplier: {po.supplier.name}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {actions
            .filter((a) => a.visible)
            .map((a) => (
              <Button key={a.action} variant={a.variant ?? "primary"} onClick={() => setPendingAction(a.action)}>
                {a.label}
              </Button>
            ))}
          {canReceiveNow && <Button onClick={() => setReceiveModalOpen(true)}>Receive Stock</Button>}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="p-5 lg:col-span-2">
          <h2 className="mb-4 text-sm font-semibold text-slate-900">Line Items</h2>
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead>
              <tr className="text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <th className="py-2">Product ID</th>
                <th className="py-2">Quantity</th>
                <th className="py-2">Received</th>
                <th className="py-2">Unit Price</th>
                <th className="py-2 text-right">Line Total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {po.items.map((item) => (
                <tr key={item.id}>
                  <td className="py-2">{item.product_id}</td>
                  <td className="py-2">{item.quantity}</td>
                  <td className="py-2">{item.received_quantity}</td>
                  <td className="py-2">{formatCurrency(item.unit_price)}</td>
                  <td className="py-2 text-right">
                    {formatCurrency(Number(item.unit_price) * item.quantity)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={4} className="pt-3 text-right text-sm font-medium text-slate-600">
                  Total
                </td>
                <td className="pt-3 text-right text-sm font-semibold text-slate-900">
                  {formatCurrency(po.total)}
                </td>
              </tr>
            </tfoot>
          </table>
          {po.notes && (
            <div className="mt-4 rounded-md bg-slate-50 p-3 text-sm text-slate-600">
              <span className="font-medium text-slate-700">Notes: </span>
              {po.notes}
            </div>
          )}
        </Card>

        <Card className="p-5">
          <h2 className="mb-4 text-sm font-semibold text-slate-900">Details</h2>
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-500">Created by</dt>
              <dd className="font-medium text-slate-800">{po.creator.full_name}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Created</dt>
              <dd className="text-slate-800">{formatDateTime(po.created_at)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Expected delivery</dt>
              <dd className="text-slate-800">{formatDate(po.expected_delivery_date)}</dd>
            </div>
            {po.approver && (
              <>
                <div className="flex justify-between">
                  <dt className="text-slate-500">Approved by</dt>
                  <dd className="font-medium text-slate-800">{po.approver.full_name}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-500">Approved at</dt>
                  <dd className="text-slate-800">{formatDateTime(po.approved_at)}</dd>
                </div>
              </>
            )}
          </dl>
        </Card>
      </div>

      <ConfirmDialog
        isOpen={pendingAction !== null}
        title={pendingAction === "cancel" ? "Cancel Purchase Order" : "Confirm Action"}
        message={
          pendingAction === "cancel"
            ? "This will cancel the purchase order. This action cannot be undone."
            : "Are you sure you want to proceed?"
        }
        confirmLabel={pendingAction === "cancel" ? "Cancel Order" : "Confirm"}
        variant={pendingAction === "cancel" ? "danger" : "primary"}
        isLoading={pendingAction !== null && mutationForAction[pendingAction].isPending}
        onConfirm={() => pendingAction && runTransition(pendingAction)}
        onCancel={() => setPendingAction(null)}
      />

      <ReceivePurchaseOrderModal
        isOpen={isReceiveModalOpen}
        onClose={() => setReceiveModalOpen(false)}
        purchaseOrder={po}
        onSubmit={handleReceive}
        isSubmitting={receiveMutation.isPending}
      />
    </div>
  );
}
