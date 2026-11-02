import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { useApprovalQueue } from "@/api/approvals";
import { extractErrorMessage } from "@/api/client";
import {
  useApproveInvoice,
  useInvoice,
  useInvoiceReasonAction,
  useInvoiceTransition,
  useRecordPayment,
  useRejectInvoice,
  type Invoice,
  type PaymentInput,
} from "@/api/supplierInvoices";
import { ApprovalTimeline } from "@/components/approvals/ApprovalTimeline";
import { DecisionDialog } from "@/components/approvals/DecisionDialog";
import { DocumentActionBar } from "@/components/layout/DocumentActionBar";
import { SummaryList, type SummaryRow } from "@/components/layout/SummaryList";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { LifecycleStepper } from "@/components/ui/LifecycleStepper";
import { LoadingState } from "@/components/ui/LoadingState";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useToast } from "@/components/ui/toast-context";
import { useAuth } from "@/lib/auth-context";
import { formatDate, formatDateTime, formatMoney } from "@/lib/format";

import { invoiceActions, invoiceSteps } from "./invoice-rules";
import { InvoiceLines } from "./InvoiceLines";
import { InvoicePayments } from "./InvoicePayments";
import { InvoiceReasonDialog } from "./InvoiceReasonDialog";
import { RecordPaymentModal } from "./RecordPaymentModal";

// The API caps a page at 100 items.
const QUEUE_LOOKUP_SIZE = 100;

type Dialog = "approve" | "reject" | "hold" | "void" | "pay" | null;

function summaryRows(invoice: Invoice): SummaryRow[] {
  const money = (value: string) => formatMoney(value, invoice.currency_code);
  return [
    { label: "Supplier", value: invoice.supplier.name },
    {
      label: "Purchase order",
      value: (
        <Link to={`/purchase-orders/${invoice.purchase_order.id}`} className="text-brand hover:underline">
          {invoice.purchase_order.po_number}
        </Link>
      ),
    },
    { label: "Invoice date", value: formatDate(invoice.invoice_date) },
    { label: "Due", value: formatDate(invoice.due_date) },
    { label: "Total", value: money(invoice.grand_total), numeric: true },
    { label: "Paid", value: money(invoice.paid_total), numeric: true },
    { label: "Open", value: money(invoice.open_amount), numeric: true },
    { label: "Recorded by", value: invoice.creator.full_name },
    ...(invoice.approver
      ? [
          { label: "Approved by", value: invoice.approver.full_name },
          { label: "Approved", value: formatDateTime(invoice.approved_at) },
        ]
      : []),
  ];
}

function statusNote(invoice: Invoice): string | null {
  if (invoice.status === "on_hold" && invoice.hold_reason) return `On hold: ${invoice.hold_reason}`;
  if (invoice.status === "void" && invoice.void_reason) return `Voided: ${invoice.void_reason}`;
  if (invoice.status === "draft" && invoice.rejection_reason) return `Sent back: ${invoice.rejection_reason}`;
  return null;
}

export function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user, hasPermission } = useAuth();
  const { showToast } = useToast();
  const invoiceId = id ? Number(id) : undefined;

  const { data: invoice, isLoading, isError } = useInvoice(invoiceId);
  const { data: queue } = useApprovalQueue(1, QUEUE_LOOKUP_SIZE);
  const submitMutation = useInvoiceTransition("submit");
  const releaseMutation = useInvoiceTransition("release");
  const approveMutation = useApproveInvoice();
  const rejectMutation = useRejectInvoice();
  const holdMutation = useInvoiceReasonAction("hold");
  const voidMutation = useInvoiceReasonAction("void");
  const payMutation = useRecordPayment(invoiceId ?? 0);
  const [dialog, setDialog] = useState<Dialog>(null);

  if (isLoading) return <LoadingState label="Loading invoice…" />;
  if (isError || !invoice) return <ErrorState message="Invoice not found." />;

  const flags = invoiceActions(invoice, { id: user?.id ?? -1, hasPermission }, queue?.items);
  const note = statusNote(invoice);

  // One place for the success toast, the error toast and closing the dialog, whichever action ran.
  const run = async (action: () => Promise<unknown>, success: string) => {
    try {
      await action();
      showToast(success);
      setDialog(null);
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  const pay = (input: PaymentInput) => run(() => payMutation.mutateAsync(input), "Payment recorded");

  return (
    <div className="space-y-6">
      <PageHeader
        title={invoice.invoice_number}
        description={`Supplier: ${invoice.supplier.name}`}
        breadcrumbs={[{ label: "Invoices", to: "/invoices" }, { label: invoice.invoice_number }]}
        secondaryActions={<StatusBadge status={invoice.status} />}
      />

      <Card padding="md">
        <LifecycleStepper label="Invoice progress" steps={invoiceSteps(invoice)} />
        {note && <p className="mt-3 text-sm text-text-secondary">{note}</p>}
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <InvoiceLines invoice={invoice} />
        <SummaryList rows={summaryRows(invoice)} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {invoice.status !== "draft" && <ApprovalTimeline documentType="invoice_exception" documentId={invoice.id} />}
        <InvoicePayments invoice={invoice} />
      </div>

      <DocumentActionBar>
        {flags.needsAnotherApprover && (
          <p className="mr-auto self-center text-sm text-text-secondary">
            You recorded this invoice, so another approver must approve it.
          </p>
        )}
        {flags.canSubmit && (
          <Button
            disabled={submitMutation.isPending}
            onClick={() => void run(() => submitMutation.mutateAsync(invoice.id), "Invoice submitted and matched")}
          >
            Submit for matching
          </Button>
        )}
        {flags.canDecide && <Button onClick={() => setDialog("approve")}>Approve</Button>}
        {flags.canDecide && (
          <Button variant="danger" onClick={() => setDialog("reject")}>
            Reject
          </Button>
        )}
        {flags.canPay && <Button onClick={() => setDialog("pay")}>Record payment</Button>}
        {flags.canRelease && (
          <Button
            variant="secondary"
            disabled={releaseMutation.isPending}
            onClick={() => void run(() => releaseMutation.mutateAsync(invoice.id), "Invoice released")}
          >
            Release hold
          </Button>
        )}
        {flags.canHold && (
          <Button variant="secondary" onClick={() => setDialog("hold")}>
            Put on hold
          </Button>
        )}
        {flags.canVoid && (
          <Button variant="danger" onClick={() => setDialog("void")}>
            Void invoice
          </Button>
        )}
      </DocumentActionBar>

      <DecisionDialog
        isOpen={dialog === "approve"}
        mode="approve"
        subject={`${invoice.invoice_number} · ${invoice.supplier.name}`}
        isSubmitting={approveMutation.isPending}
        onClose={() => setDialog(null)}
        onSubmit={(comment) =>
          void run(() => approveMutation.mutateAsync({ id: invoice.id, comment }), "Invoice approved")
        }
      />
      <DecisionDialog
        isOpen={dialog === "reject"}
        mode="reject"
        subject={`${invoice.invoice_number} · ${invoice.supplier.name}`}
        notice="A rejected invoice goes back to draft so it can be corrected and submitted again."
        isSubmitting={rejectMutation.isPending}
        onClose={() => setDialog(null)}
        onSubmit={(comment) =>
          void run(() => rejectMutation.mutateAsync({ id: invoice.id, comment }), "Invoice sent back to draft")
        }
      />
      <InvoiceReasonDialog
        isOpen={dialog === "hold"}
        title="Put invoice on hold"
        subject={`${invoice.invoice_number} · it cannot be approved or paid until released.`}
        confirmLabel="Put on hold"
        isSubmitting={holdMutation.isPending}
        onClose={() => setDialog(null)}
        onSubmit={(reason) => void run(() => holdMutation.mutateAsync({ id: invoice.id, reason }), "Invoice on hold")}
      />
      <InvoiceReasonDialog
        isOpen={dialog === "void"}
        title="Void invoice"
        subject={`${invoice.invoice_number} · a voided invoice no longer counts for matching or payables. This cannot be undone.`}
        confirmLabel="Void invoice"
        isSubmitting={voidMutation.isPending}
        onClose={() => setDialog(null)}
        onSubmit={(reason) => void run(() => voidMutation.mutateAsync({ id: invoice.id, reason }), "Invoice voided")}
      />
      <RecordPaymentModal
        isOpen={dialog === "pay"}
        invoice={invoice}
        isSubmitting={payMutation.isPending}
        onClose={() => setDialog(null)}
        onSubmit={(input) => void pay(input)}
      />
    </div>
  );
}
