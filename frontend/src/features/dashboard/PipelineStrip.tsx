import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

import type { DashboardSummary } from "@/api/types";
import { Card } from "@/components/ui/Card";
import { formatNumber } from "@/lib/format";

interface Stage {
  label: string;
  value: number;
  to: string;
}

function stagesOf(summary: DashboardSummary): Stage[] {
  return [
    { label: "Orders raised", value: summary.total_purchase_orders, to: "/purchase-orders" },
    { label: "Pending", value: summary.pending_orders, to: "/purchase-orders" },
    { label: "Deliveries due", value: summary.upcoming_deliveries, to: "/deliveries" },
    { label: "Completed", value: summary.completed_orders, to: "/purchase-orders" },
  ];
}

/** The order pipeline at a glance; each stage links to the list it counts. */
export function PipelineStrip({ summary }: { summary: DashboardSummary }) {
  const stages = stagesOf(summary);
  return (
    <Card padding="md">
      <h2 className="mb-3 text-title text-text-primary">Order pipeline</h2>
      <ol className="flex flex-col gap-2 sm:flex-row sm:items-stretch">
        {stages.map((stage, index) => (
          <li key={stage.label} className="flex flex-1 items-center gap-2">
            <Link
              to={stage.to}
              className="flex-1 rounded-control border border-border bg-bg px-4 py-3 transition-colors duration-fast hover:border-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              <p className="text-caption uppercase text-text-secondary">{stage.label}</p>
              <p className="text-display-sm tabular-nums text-text-primary">{formatNumber(stage.value)}</p>
            </Link>
            {index < stages.length - 1 && (
              <ArrowRight aria-hidden="true" className="hidden h-4 w-4 shrink-0 text-text-muted sm:block" />
            )}
          </li>
        ))}
      </ol>
    </Card>
  );
}
