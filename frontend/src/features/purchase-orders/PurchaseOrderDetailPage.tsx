import { ArrowLeft } from "lucide-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { useApprovalQueue } from "@/api/approvals";
import { useCostCentres } from "@/api/budgets";
import { extractErrorMessage } from "@/api/client";
import {
  useAmendPurchaseOrder,
  usePurchaseOrder,
  usePurchaseOrderTransition,
  useReceivePurchaseOrder,
  useRejectPurchaseOrder,
  type AmendInput,
} from "@/api/purchaseOrders";
import { ApprovalTimeline } from "@/components/approvals/ApprovalTimeline";
import { DecisionDialog } from "@/components/approvals/DecisionDialog";
import { Attachments } from "@/components/attachments/Attachments";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingState";
import { useToast } from "@/components/ui/toast-context";
import { useAuth } from "@/lib/auth-context";
import { formatDate, formatDateTime } from "@/lib/utils";

import { canDecidePurchaseOrder, needsAnotherApprover } from "./approval";
import { AmendPurchaseOrderModal } from "./AmendPurchaseOrderModal";
import { PurchaseOrderDocumentActions } from "./PurchaseOrderDocumentActions";
import { PurchaseOrderLines } from "./PurchaseOrderLines";
import { ReceivePurchaseOrderModal } from "./ReceivePurchaseOrderModal";
import { VersionsPanel } from "./VersionsPanel";

// The API caps a page at 100 items.
const QUEUE_LOOKUP_SIZE = 100;
const AMENDABLE_STATUSES = ["approved", "ordered", "partially_received"];

type PendingAction = "submit" | "approve" | "order" | "cancel" | null;

export function PurchaseOrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user, hasPermission } = useAuth();
  const { showToast } = useToast();
  const poId = id ? Number(id) : undefined;

  const { data: po, isLoading, isError } = usePurchaseOrder(poId);
  const submitMutation = usePurchaseOrderTransition("submit");
  const approveMutation = usePurchaseOrderTransition("approve");
  const orderMutation = usePurchaseOrderTransition("order");
  const cancelMutation = usePurchaseOrderTransition("cancel");
  const receiveMutation = useReceivePurchaseOrder();
  const rejectMutation = useRejectPurchaseOrder();
  const amendMutation = useAmendPurchaseOrder();
  const { data: queue } = useApprovalQueue(1, QUEUE_LOOKUP_SIZE);
  const { data: costCentres } = useCostCentres();

  const [pendingAction, setPendingAction] = useState<PendingAction>(null);
  const [isReceiveModalOpen, setReceiveModalOpen] = useState(false);
  const [isRejectOpen, setRejectOpen] = useState(false);
  const [isAmendOpen, setAmendOpen] = useState(false);

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

  const handleReject = async (comment: string) => {
    try {
      await rejectMutation.mutateAsync({ id: po.id, comment });
      showToast("Purchase order rejected and cancelled");
      setRejectOpen(false);
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  const handleAmend = async (input: AmendInput) => {
    try {
      const version = await amendMutation.mutateAsync({ id: po.id, ...input });
      showToast(version.status === "applied" ? "Change applied" : "Change sent for approval");
      setAmendOpen(false);
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  const canCreate = hasPermission("po:create");
  const canApprove = canDecidePurchaseOrder(po, queue?.items);
  const showApproverHint = needsAnotherApprover(po, user, hasPermission, queue?.items);
  const costCentre = costCentres?.find((centre) => centre.id === po.cost_centre_id);
  const canAmend = AMENDABLE_STATUSES.includes(po.status) && hasPermission("po:transition");
  const showVersions = !["draft", "submitted"].includes(po.status);
  const canTransition = hasPermission("po:transition");
  const canReceive = hasPermission("inventory:write");

  const actions: {
    label: string;
    action: Exclude<PendingAction, null>;
    visible: boolean;
    variant?: "primary" | "danger";
  }[] = [
    { label: "Submit for Approval", action: "submit", visible: po.status === "draft" && canCreate },
    { label: "Approve", action: "approve", visible: canApprove },
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
        onClick={() => void navigate("/purchase-orders")}
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
          <PurchaseOrderDocumentActions
            poId={po.id}
            poNumber={po.po_number}
            canSend={po.status === "ordered" && canTransition}
          />
          {actions
            .filter((a) => a.visible)
            .map((a) => (
              <Button key={a.action} variant={a.variant ?? "primary"} onClick={() => setPendingAction(a.action)}>
                {a.label}
              </Button>
            ))}
          {canApprove && (
            <Button variant="danger" onClick={() => setRejectOpen(true)}>
              Reject
            </Button>
          )}
          {canAmend && (
            <Button variant="secondary" onClick={() => setAmendOpen(true)}>
              Amend
            </Button>
          )}
          {canReceiveNow && <Button onClick={() => setReceiveModalOpen(true)}>Receive Stock</Button>}
          {showApproverHint && (
            <p className="self-center text-sm text-slate-500">
              You created this order, so another approver must approve it.
            </p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <PurchaseOrderLines po={po} />

        <Card className="p-5">
          <h2 className="mb-4 text-sm font-semibold text-slate-900">Details</h2>
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-500">Currency</dt>
              <dd className="font-medium text-slate-800">{po.currency_code}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Cost centre</dt>
              <dd className="text-slate-800">{costCentre ? `${costCentre.code} — ${costCentre.name}` : "—"}</dd>
            </div>
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

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ApprovalTimeline documentType="purchase_order" documentId={po.id} />
        <Attachments parentType="purchase_order" parentId={po.id} canWrite={canCreate} />
      </div>
      {showVersions && <VersionsPanel po={po} />}

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
        onConfirm={() => {
          if (pendingAction) void runTransition(pendingAction);
        }}
        onCancel={() => setPendingAction(null)}
      />

      <DecisionDialog
        isOpen={isRejectOpen}
        mode="reject"
        subject={`${po.po_number} · ${po.supplier.name}`}
        notice="A rejected purchase order is cancelled. The creator can raise a new one."
        isSubmitting={rejectMutation.isPending}
        onClose={() => setRejectOpen(false)}
        onSubmit={(comment) => void handleReject(comment)}
      />
      <AmendPurchaseOrderModal
        isOpen={isAmendOpen}
        po={po}
        isSubmitting={amendMutation.isPending}
        onClose={() => setAmendOpen(false)}
        onSubmit={handleAmend}
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
