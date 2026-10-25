import { ArrowLeft } from "lucide-react";
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
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingState";
import { useToast } from "@/components/ui/toast-context";
import { useAuth } from "@/lib/auth-context";
import { formatCurrency, formatDate, formatDateTime } from "@/lib/utils";

import { ConvertRequestModal } from "./ConvertRequestModal";
import { RequestFormModal } from "./RequestFormModal";

type Dialog = "edit" | "cancel" | "approve" | "reject" | "convert" | null;

function LinesCard({ request }: { request: PurchaseRequest }) {
  return (
    <Card className="overflow-x-auto lg:col-span-2">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50 text-left text-xs font-semibold uppercase text-slate-500">
          <tr>
            <th className="px-4 py-3">Description</th>
            <th className="px-4 py-3 text-right">Quantity</th>
            <th className="px-4 py-3 text-right">Unit price</th>
            <th className="px-4 py-3 text-right">Line total</th>
            <th className="px-4 py-3">Order</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
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
                  <Link to={`/purchase-orders/${line.converted_po_id}`} className="text-brand-700 hover:underline">
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
          <tr className="bg-slate-50 font-semibold">
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
      <button
        onClick={() => void navigate("/requests")}
        className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700"
      >
        <ArrowLeft className="h-4 w-4" /> Back to requests
      </button>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold text-slate-900">{request.request_number}</h1>
            <Badge status={request.status}>{request.status}</Badge>
          </div>
          <p className="text-sm text-slate-500">{request.title}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {isOwner && isEditable && (
            <>
              <Button variant="secondary" onClick={() => setDialog("edit")}>
                Edit
              </Button>
              <Button
                disabled={submitAction.isPending}
                onClick={() =>
                  void attempt(() => submitAction.mutateAsync({ id: request.id }), "Request submitted", false)
                }
              >
                Submit
              </Button>
            </>
          )}
          {showDecision && (
            <>
              <Button onClick={() => setDialog("approve")}>Approve</Button>
              <Button variant="danger" onClick={() => setDialog("reject")}>
                Reject
              </Button>
            </>
          )}
          {canConvert && <Button onClick={() => setDialog("convert")}>Create purchase orders</Button>}
          {canCancel && (
            <Button variant="danger" onClick={() => setDialog("cancel")}>
              Cancel request
            </Button>
          )}
        </div>
      </div>

      {request.status === "rejected" && request.rejection_reason && (
        <p role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          Rejected: {request.rejection_reason}
        </p>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <LinesCard request={request} />
        <Card className="p-5">
          <h2 className="mb-4 text-sm font-semibold text-slate-900">Details</h2>
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">Requested by</dt>
              <dd className="font-medium text-slate-800">{request.requester.full_name}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">Cost centre</dt>
              <dd className="text-slate-800">{costCentre ? `${costCentre.code} — ${costCentre.name}` : "—"}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">Currency</dt>
              <dd className="text-slate-800">{request.currency_code}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">Needed by</dt>
              <dd className="text-slate-800">{formatDate(request.needed_by)}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">Submitted</dt>
              <dd className="text-slate-800">{formatDateTime(request.submitted_at)}</dd>
            </div>
            {request.base_estimated_total !== null && (
              <div className="flex justify-between gap-3">
                <dt className="text-slate-500">In company currency</dt>
                <dd className="tabular-nums text-slate-800">{formatCurrency(request.base_estimated_total)}</dd>
              </div>
            )}
          </dl>
          {request.notes && (
            <p className="mt-4 whitespace-pre-wrap border-t border-slate-100 pt-3 text-sm text-slate-600">
              {request.notes}
            </p>
          )}
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ApprovalTimeline documentType="purchase_request" documentId={request.id} />
        <Attachments parentType="purchase_request" parentId={request.id} canWrite={canCancel} />
      </div>

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
