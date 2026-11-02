import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { useCostCentres } from "@/api/budgets";
import { extractErrorMessage } from "@/api/client";
import {
  useConvertRequest,
  useRejectRequest,
  useRequest,
  useRequestAction,
  useUpdateRequest,
  type ConvertInput,
  type PurchaseRequestInput,
} from "@/api/purchaseRequests";
import type { PurchaseRequest } from "@/api/types";
import { ApprovalTimeline } from "@/components/approvals/ApprovalTimeline";
import { DecisionDialog } from "@/components/approvals/DecisionDialog";
import { useIsInQueue } from "@/components/approvals/useIsInQueue";
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
import { formatCurrency, formatDate, formatDateTime } from "@/lib/utils";

import { ConvertRequestModal } from "./ConvertRequestModal";
import { RequestFormModal } from "./RequestFormModal";

type Dialog = "edit" | "cancel" | "approve" | "reject" | "convert" | null;

const FLOW: Array<{ id: PurchaseRequest["status"]; label: string }> = [
  { id: "draft", label: "Draft" },
  { id: "submitted", label: "Submitted" },
  { id: "approved", label: "Approved" },
  { id: "converted", label: "Ordered" },
];

/** Where the request is in draft, submit, approve, order; a rejection marks the step it stopped at. */
function requestSteps(request: PurchaseRequest): LifecycleStep[] {
  const reached =
    request.status === "rejected"
      ? 1
      : Math.max(
          0,
          FLOW.findIndex((step) => step.id === request.status),
        );
  return FLOW.map((step, index) => ({
    id: step.id,
    label: step.label,
    state:
      request.status === "rejected" && index === reached
        ? "rejected"
        : index < reached || (index === reached && request.status === "converted")
          ? "done"
          : index === reached
            ? "current"
            : "upcoming",
  }));
}

function LinesCard({ request }: { request: PurchaseRequest }) {
  return (
    <Card className="overflow-x-auto lg:col-span-2">
      <table className="min-w-full divide-y divide-border text-sm">
        <thead className="bg-bg text-left text-caption uppercase text-text-secondary">
          <tr>
            <th className="px-4 py-3">Description</th>
            <th className="px-4 py-3 text-right">Quantity</th>
            <th className="px-4 py-3 text-right">Unit price</th>
            <th className="px-4 py-3 text-right">Line total</th>
            <th className="px-4 py-3">Order</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {request.lines.map((line) => (
            <tr key={line.id}>
              <td className="px-4 py-3">{line.description}</td>
              <td className="px-4 py-3 text-right tabular-nums">
                {line.quantity} {line.unit}
              </td>
              <td className="px-4 py-3 text-right tabular-nums">
                {formatCurrency(line.estimated_unit_price, request.currency_code)}
              </td>
              <td className="px-4 py-3 text-right tabular-nums">
                {formatCurrency(line.line_total, request.currency_code)}
              </td>
              <td className="px-4 py-3">
                {line.converted_po_id !== null ? (
                  <Link to={`/purchase-orders/${line.converted_po_id}`} className="text-brand hover:underline">
                    View order
                  </Link>
                ) : (
                  "—"
                )}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="bg-bg font-semibold">
            <td className="px-4 py-3" colSpan={3}>
              Estimated total
            </td>
            <td className="px-4 py-3 text-right tabular-nums">
              {formatCurrency(request.estimated_total, request.currency_code)}
            </td>
            <td />
          </tr>
        </tfoot>
      </table>
    </Card>
  );
}

export function RequestDetailPage() {
  const { id } = useParams<{ id: string }>();
  const requestId = id ? Number(id) : undefined;
  const navigate = useNavigate();
  const { user, hasPermission } = useAuth();
  const { showToast } = useToast();
  const [dialog, setDialog] = useState<Dialog>(null);

  const { data: request, isLoading, isError } = useRequest(requestId);
  const { data: costCentres } = useCostCentres();
  const canDecide = useIsInQueue("purchase_request", requestId);
  const update = useUpdateRequest();
  const submitAction = useRequestAction("submit");
  const cancelAction = useRequestAction("cancel");
  const approveAction = useRequestAction("approve");
  const rejectAction = useRejectRequest();
  const convert = useConvertRequest();

  if (isLoading) return <LoadingState label="Loading request…" />;
  if (isError || !request) return <ErrorState message="Request not found." />;

  const isOwner = user !== null && request.requester.id === user.id && hasPermission("request:create");
  const isEditable = request.status === "draft" || request.status === "rejected";
  const canCancel = isOwner && (isEditable || request.status === "submitted");
  const showDecision = canDecide && request.status === "submitted";
  const canConvert = hasPermission("po:create") && request.status === "approved";
  const costCentre = costCentres?.find((centre) => centre.id === request.cost_centre_id);

  const attempt = async (work: () => Promise<unknown>, success: string, closeDialog = true) => {
    try {
      await work();
      showToast(success);
      if (closeDialog) setDialog(null);
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  const handleEdit = (input: PurchaseRequestInput) =>
    attempt(() => update.mutateAsync({ id: request.id, ...input }), "Request updated");

  const handleConvert = (input: ConvertInput) =>
    attempt(async () => {
      const result = await convert.mutateAsync({ id: request.id, ...input });
      const [first] = result.purchase_order_ids;
      if (first !== undefined) void navigate(`/purchase-orders/${first}`);
    }, "Draft purchase orders created");

  return (
    <div className="space-y-6">
      <PageHeader
        title={request.request_number}
        description={request.title}
        breadcrumbs={[{ label: "Requests", to: "/requests" }, { label: request.request_number }]}
        secondaryActions={<StatusBadge status={request.status} />}
      />

      <Card padding="md">
        <LifecycleStepper label="Request progress" steps={requestSteps(request)} />
      </Card>

      {request.status === "rejected" && request.rejection_reason && (
        <p role="alert" className="rounded-control bg-danger-bg p-3 text-sm text-danger-fg">
          Rejected: {request.rejection_reason}
        </p>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <LinesCard request={request} />
        <SummaryList
          rows={[
            { label: "Requested by", value: request.requester.full_name },
            { label: "Cost centre", value: costCentre ? `${costCentre.code} — ${costCentre.name}` : "—" },
            { label: "Currency", value: request.currency_code },
            { label: "Needed by", value: formatDate(request.needed_by) },
            { label: "Submitted", value: formatDateTime(request.submitted_at) },
            ...(request.base_estimated_total !== null
              ? [{ label: "In company currency", value: formatCurrency(request.base_estimated_total), numeric: true }]
              : []),
          ]}
          footer={request.notes ? <p className="whitespace-pre-wrap">{request.notes}</p> : undefined}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ApprovalTimeline documentType="purchase_request" documentId={request.id} />
        <Attachments parentType="purchase_request" parentId={request.id} canWrite={canCancel} />
      </div>

      <DocumentActionBar>
        {isOwner && isEditable && (
          <Button variant="secondary" onClick={() => setDialog("edit")}>
            Edit
          </Button>
        )}
        {isOwner && isEditable && (
          <Button
            disabled={submitAction.isPending}
            onClick={() => void attempt(() => submitAction.mutateAsync({ id: request.id }), "Request submitted", false)}
          >
            Submit
          </Button>
        )}
        {showDecision && <Button onClick={() => setDialog("approve")}>Approve</Button>}
        {showDecision && (
          <Button variant="danger" onClick={() => setDialog("reject")}>
            Reject
          </Button>
        )}
        {canConvert && <Button onClick={() => setDialog("convert")}>Create purchase orders</Button>}
        {canCancel && (
          <Button variant="danger" onClick={() => setDialog("cancel")}>
            Cancel request
          </Button>
        )}
      </DocumentActionBar>

      <RequestFormModal
        isOpen={dialog === "edit"}
        request={request}
        isSubmitting={update.isPending}
        onClose={() => setDialog(null)}
        onSubmit={handleEdit}
      />
      <ConfirmDialog
        isOpen={dialog === "cancel"}
        title="Cancel request"
        message="This withdraws the request. It cannot be undone."
        confirmLabel="Cancel request"
        variant="danger"
        isLoading={cancelAction.isPending}
        onConfirm={() => void attempt(() => cancelAction.mutateAsync({ id: request.id }), "Request cancelled")}
        onCancel={() => setDialog(null)}
      />
      <DecisionDialog
        isOpen={dialog === "approve" || dialog === "reject"}
        mode={dialog === "reject" ? "reject" : "approve"}
        subject={`${request.request_number} · ${request.title}`}
        isSubmitting={approveAction.isPending || rejectAction.isPending}
        onClose={() => setDialog(null)}
        onSubmit={(comment) =>
          void (dialog === "reject"
            ? attempt(() => rejectAction.mutateAsync({ id: request.id, comment }), "Request rejected")
            : attempt(
                () => approveAction.mutateAsync({ id: request.id, comment: comment || undefined }),
                "Request approved",
              ))
        }
      />
      <ConvertRequestModal
        isOpen={dialog === "convert"}
        request={request}
        isSubmitting={convert.isPending}
        onClose={() => setDialog(null)}
        onSubmit={(input) => void handleConvert(input)}
      />
    </div>
  );
}
