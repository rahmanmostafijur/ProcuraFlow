import { extractErrorMessage } from "@/api/client";
import { useCancelPaymentRun, useReleasePaymentRun, type PaymentRun } from "@/api/paymentRuns";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/toast-context";
import { useAuth } from "@/lib/auth-context";
import { formatCurrency, formatDateTime } from "@/lib/utils";

import { PaymentFilePanel } from "./PaymentFilePanel";

export function PaymentRunModal({ run, onClose }: { run: PaymentRun | null; onClose: () => void }) {
  const { hasPermission } = useAuth();
  const { showToast } = useToast();
  const release = useReleasePaymentRun();
  const cancel = useCancelPaymentRun();

  const act = async (action: typeof release, message: string) => {
    if (!run) return;
    try {
      await action.mutateAsync(run.id);
      showToast(message);
      onClose();
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  const isDraft = run?.status === "draft";

  return (
    <Modal isOpen={run !== null} onClose={onClose} title={run ? `Payment run ${run.number}` : "Payment run"} size="lg">
      {run && (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-sm">
            <Badge status={run.status}>{run.status}</Badge>
            <span className="font-semibold">{formatCurrency(run.total, run.currency_code)}</span>
          </div>
          <p className="text-xs text-text-secondary">
            Created by {run.creator.full_name} on {formatDateTime(run.created_at)}
            {run.releaser && run.released_at
              ? ` · released by ${run.releaser.full_name} on ${formatDateTime(run.released_at)}`
              : ""}
          </p>
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-text-secondary">
              <tr>
                <th className="py-2 pr-3">Supplier</th>
                <th className="py-2 pr-3">Invoice</th>
                <th className="py-2 text-right">Amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {run.items.map((item) => (
                <tr key={item.id}>
                  <td className="py-2 pr-3">{item.supplier_name}</td>
                  <td className="py-2 pr-3">{item.invoice_number}</td>
                  <td className="py-2 text-right">{formatCurrency(item.amount, run.currency_code)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {run.status === "released" && hasPermission("payment:export") && <PaymentFilePanel runId={run.id} />}
          {isDraft && (
            <div className="flex justify-end gap-2">
              {hasPermission("payment:write") && (
                <Button
                  variant="secondary"
                  disabled={cancel.isPending}
                  onClick={() => void act(cancel, "Run cancelled")}
                >
                  Cancel run
                </Button>
              )}
              {hasPermission("payment:release") && (
                <Button disabled={release.isPending} onClick={() => void act(release, "Run released")}>
                  Release run
                </Button>
              )}
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}
