import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { useApprovalQueue } from "@/api/approvals";
import { useBudgetPositions } from "@/api/budgets";
import { useRecentActivity } from "@/api/dashboard";
import { useExpiringDocuments } from "@/api/supplierDocuments";
import { Card } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/LoadingState";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatCompactMoney, formatDate, formatDateTime, formatMoney, formatPercent } from "@/lib/format";

const LIST_LIMIT = 5;

interface CardShellProps {
  title: string;
  to?: string;
  children: ReactNode;
}

function CardShell({ title, to, children }: CardShellProps) {
  return (
    <Card padding="md" className="flex flex-col">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-title text-text-primary">{title}</h2>
        {to && (
          <Link to={to} className="text-sm font-medium text-brand underline-offset-2 hover:underline">
            View all
          </Link>
        )}
      </div>
      {children}
    </Card>
  );
}

function Empty({ children }: { children: string }) {
  return <p className="py-8 text-center text-sm text-text-secondary">{children}</p>;
}

export function WaitingForYouCard() {
  const { data, isLoading } = useApprovalQueue(1, LIST_LIMIT);
  return (
    <CardShell title="Waiting for you" to="/approvals">
      {isLoading || !data ? (
        <LoadingState />
      ) : data.items.length === 0 ? (
        <Empty>Nothing is waiting for your approval.</Empty>
      ) : (
        <ul className="divide-y divide-border">
          {data.items.map((item) => (
            <li
              key={`${item.document_type}-${item.document_id}`}
              className="flex items-center justify-between gap-3 py-2 text-sm"
            >
              <div className="min-w-0">
                <p className="truncate font-medium text-text-primary">{item.label}</p>
                <p className="truncate text-text-secondary">{item.requester.full_name}</p>
              </div>
              <span className="tabular-nums text-text-primary">{formatMoney(item.amount_base)}</span>
            </li>
          ))}
        </ul>
      )}
    </CardShell>
  );
}

export function BudgetHealthCard() {
  const { data, isLoading } = useBudgetPositions();
  return (
    <CardShell title="Budget health" to="/budgets">
      {isLoading || !data ? (
        <LoadingState />
      ) : data.length === 0 ? (
        <Empty>No budgets are set for this year.</Empty>
      ) : (
        <ul className="space-y-3">
          {data.slice(0, LIST_LIMIT).map((position) => (
            <li key={position.budget_id} className="space-y-1 text-sm">
              <div className="flex items-center justify-between gap-2">
                <span className="truncate font-medium text-text-primary">{position.cost_centre_name}</span>
                <span className="flex items-center gap-2">
                  <span className="tabular-nums text-text-secondary">
                    {position.utilisation_percent === null ? "–" : formatPercent(position.utilisation_percent)}
                  </span>
                  <StatusBadge status={position.health} />
                </span>
              </div>
              <p className="tabular-nums text-text-secondary">
                {formatCompactMoney(position.remaining)} left of {formatCompactMoney(position.budget)}
              </p>
            </li>
          ))}
        </ul>
      )}
    </CardShell>
  );
}

export function ExpiringDocumentsCard() {
  const { data, isLoading } = useExpiringDocuments();
  return (
    <CardShell title="Documents expiring soon" to="/suppliers/expiring-documents">
      {isLoading || !data ? (
        <LoadingState />
      ) : data.length === 0 ? (
        <Empty>No supplier documents are expiring.</Empty>
      ) : (
        <ul className="divide-y divide-border">
          {data.slice(0, LIST_LIMIT).map((doc) => (
            <li key={doc.id} className="flex items-center justify-between gap-3 py-2 text-sm">
              <div className="min-w-0">
                <p className="truncate font-medium text-text-primary">{doc.supplier_name}</p>
                <p className="truncate capitalize text-text-secondary">{doc.document_type.replace(/_/g, " ")}</p>
              </div>
              <span className="tabular-nums text-text-secondary">{formatDate(doc.expiry_date)}</span>
            </li>
          ))}
        </ul>
      )}
    </CardShell>
  );
}

// Mounted only for audit:read holders, so other roles never request a feed the API would refuse.
export function RecentActivityCard() {
  const { data: activity, isLoading } = useRecentActivity();
  return (
    <CardShell title="Recent Activity">
      {isLoading || !activity ? (
        <LoadingState />
      ) : activity.length === 0 ? (
        <Empty>No recent activity.</Empty>
      ) : (
        <ul className="space-y-3">
          {activity.map((item) => (
            <li key={item.id} className="text-sm">
              <p className="text-text-primary">
                <span className="font-medium">{item.user_name ?? "System"}</span> {item.action.replace(/_/g, " ")}
              </p>
              <p className="text-xs text-text-muted">{formatDateTime(item.created_at)}</p>
            </li>
          ))}
        </ul>
      )}
    </CardShell>
  );
}
