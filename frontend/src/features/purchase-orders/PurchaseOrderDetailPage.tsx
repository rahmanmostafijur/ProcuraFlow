import { useState } from "react";
import { useParams } from "react-router-dom";

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
import { DocumentActionBar } from "@/components/layout/DocumentActionBar";
import { SummaryList } from "@/components/layout/SummaryList";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { ErrorState } from "@/components/ui/ErrorState";
import { LifecycleStepper, type LifecycleStep } from "@/components/ui/LifecycleStepper";
import { LoadingState } from "@/components/ui/LoadingState";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
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

const ORDER_FLOW = ["draft", "submitted", "approved", "ordered", "received"] as const;
const ORDER_FLOW_LABELS = ["Draft", "Submitted", "Approved", "Ordered", "Received"];

/** Position in draft, submit, approve, order, receive; partial receipt keeps "Received" as the current step. */
function orderSteps(status: string): LifecycleStep[] {
  const index = status === "partially_received" ? 4 : ORDER_FLOW.indexOf(status as (typeof ORDER_FLOW)[number]);
  return ORDER_FLOW_LABELS.map((label, position) => ({
    id: ORDER_FLOW[position],
    label,
    state:
      status === "cancelled" || status === "rejected"
        ? "upcoming"
        : status === "received" && position === 4
          ? "done"
          : position < index
            ? "done"
            : position === index
              ? "current"
              : "upcoming",
  }));
}

export function PurchaseOrderDetailPage() {
  const { id } = useParams<{ id: string }>();
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
      <PageHeader
        title={po.po_number}
        description={`Supplier: ${po.supplier.name}`}
        breadcrumbs={[{ label: "Purchase orders", to: "/purchase-orders" }, { label: po.po_number }]}
        secondaryActions={<StatusBadge status={po.status} />}
      />

      <Card padding="md">
        <LifecycleStepper label="Order progress" steps={orderSteps(po.status)} />
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <PurchaseOrderLines po={po} />

        <SummaryList
          rows={[
            { label: "Currency", value: po.currency_code },
            { label: "Cost centre", value: costCentre ? `${costCentre.code} — ${costCentre.name}` : "—" },
            { label: "Created by", value: po.creator.full_name },
            { label: "Created", value: formatDateTime(po.created_at) },
            { label: "Expected delivery", value: formatDate(po.expected_delivery_date) },
            ...(po.approver
              ? [
                  { label: "Approved by", value: po.approver.full_name },
                  { label: "Approved at", value: formatDateTime(po.approved_at) },
                ]
              : []),
          ]}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ApprovalTimeline documentType="purchase_order" documentId={po.id} />
        <Attachments parentType="purchase_order" parentId={po.id} canWrite={canCreate} />
      </div>
      {showVersions && <VersionsPanel po={po} />}

      <DocumentActionBar>
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
          <p className="mr-auto self-center text-sm text-text-secondary">
            You created this order, so another approver must approve it.
          </p>
        )}
      </DocumentActionBar>

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
