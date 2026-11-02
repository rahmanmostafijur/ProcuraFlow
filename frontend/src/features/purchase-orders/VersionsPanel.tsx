import { extractErrorMessage } from "@/api/client";
import { usePurchaseOrderVersions, useWithdrawAmendment } from "@/api/purchaseOrders";
import type { PurchaseOrder } from "@/api/types";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useToast } from "@/components/ui/toast-context";
import { useAuth } from "@/lib/auth-context";
import { formatDateTime } from "@/lib/utils";

import { VersionDiff } from "./VersionDiff";

export function VersionsPanel({ po }: { po: PurchaseOrder }) {
  const { user } = useAuth();
  const { showToast } = useToast();
  const { data: versions, isLoading, isError } = usePurchaseOrderVersions(po.id);
  const withdraw = useWithdrawAmendment();

  const handleWithdraw = async (versionId: number) => {
    try {
      await withdraw.mutateAsync(versionId);
      showToast("Change withdrawn");
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  return (
    <Card className="p-5">
      <h2 className="mb-3 text-sm font-semibold text-text-primary">Versions</h2>
      {isLoading && <p className="text-sm text-text-secondary">Loading versions…</p>}
      {isError && <p className="text-sm text-danger-fg">The versions could not be loaded.</p>}
      {versions && versions.length === 0 && (
        <p className="text-sm text-text-secondary">This order has not been changed.</p>
      )}
      <ol className="space-y-4">
        {versions?.map((version) => (
          <li key={version.id} className="space-y-2 border-b border-border pb-4 last:border-0">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-medium text-text-primary">Version {version.version}</span>
              <StatusBadge status={version.status} label={version.status.replace(/_/g, " ")} />
              <span className="text-text-secondary">
                {version.created_by_person.full_name} · {formatDateTime(version.created_at)}
              </span>
            </div>
            <p className="text-sm text-text-secondary">Reason: {version.reason}</p>
            <VersionDiff changes={version.changes} currency={po.currency_code} />
            {version.status === "pending_approval" && user?.id === version.created_by_person.id && (
              <Button
                variant="secondary"
                size="sm"
                disabled={withdraw.isPending}
                aria-label={`Withdraw version ${version.version}`}
                onClick={() => void handleWithdraw(version.id)}
              >
                Withdraw
              </Button>
            )}
          </li>
        ))}
      </ol>
    </Card>
  );
}
