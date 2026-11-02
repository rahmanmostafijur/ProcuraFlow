import { useBudgetHistory } from "@/api/budgets";
import type { BudgetPosition } from "@/api/types";
import { Drawer } from "@/components/ui/Drawer";
import { formatCurrency, formatDateTime } from "@/lib/utils";

const CHANGE_LABELS = {
  created: "Budget set",
  adjusted: "Adjusted",
  transfer_in: "Transfer in",
  transfer_out: "Transfer out",
} as const;

interface HistoryDrawerProps {
  position: BudgetPosition | null;
  onClose: () => void;
}

export function HistoryDrawer({ position, onClose }: HistoryDrawerProps) {
  const { data: changes, isLoading, isError } = useBudgetHistory(position?.budget_id);

  return (
    <Drawer
      isOpen={position !== null}
      onClose={onClose}
      title={position ? `${position.cost_centre_code} budget history` : "Budget history"}
    >
      {isLoading && <p className="text-sm text-text-secondary">Loading history…</p>}
      {isError && <p className="text-sm text-danger-fg">The history could not be loaded.</p>}
      {changes && changes.length === 0 && <p className="text-sm text-text-secondary">No changes recorded.</p>}
      <ol className="space-y-3">
        {changes?.map((change) => (
          <li key={change.id} className="rounded-control border border-border p-3 text-sm">
            <p className="font-medium text-text-primary">{CHANGE_LABELS[change.change_type]}</p>
            <p className="tabular-nums text-text-secondary">
              {change.old_amount !== null && `${formatCurrency(change.old_amount)} → `}
              {formatCurrency(change.new_amount)}
            </p>
            {change.reason && <p className="text-text-secondary">{change.reason}</p>}
            <p className="text-xs text-text-secondary">{formatDateTime(change.created_at)}</p>
          </li>
        ))}
      </ol>
    </Drawer>
  );
}
