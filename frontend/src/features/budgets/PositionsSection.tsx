import { useState } from "react";

import type { BudgetPosition } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { ErrorState } from "@/components/ui/ErrorState";
import { formatCurrency } from "@/lib/utils";

import { HistoryDrawer } from "./HistoryDrawer";

const HEALTH_LABELS = { ok: "On track", warning: "Nearly used", over: "Over budget" } as const;

interface PositionsSectionProps {
  positions: BudgetPosition[] | undefined;
  isLoading: boolean;
  isError: boolean;
}

function money(value: string) {
  return <span className="tabular-nums">{formatCurrency(value)}</span>;
}

export function PositionsSection({ positions, isLoading, isError }: PositionsSectionProps) {
  const [historyOf, setHistoryOf] = useState<BudgetPosition | null>(null);

  const columns: Column<BudgetPosition>[] = [
    {
      header: "Cost centre",
      accessor: (row) => (
        <span className="font-medium text-slate-900">
          {row.cost_centre_code} — {row.cost_centre_name}
        </span>
      ),
    },
    { header: "Budget", accessor: (row) => money(row.budget) },
    { header: "Spent", accessor: (row) => money(row.spent) },
    { header: "Committed", accessor: (row) => money(row.committed) },
    { header: "Remaining", accessor: (row) => money(row.remaining) },
    {
      header: "Used",
      accessor: (row) => (row.utilisation_percent === null ? "—" : `${Number(row.utilisation_percent).toFixed(1)}%`),
    },
    { header: "Health", accessor: (row) => <Badge status={row.health}>{HEALTH_LABELS[row.health]}</Badge> },
    {
      header: "",
      accessor: (row) => (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          aria-label={`History of ${row.cost_centre_code}`}
          onClick={() => setHistoryOf(row)}
        >
          History
        </Button>
      ),
    },
  ];

  return (
    <Card>
      <div className="border-b border-slate-200 p-4">
        <h2 className="text-base font-semibold text-slate-900">Positions</h2>
      </div>
      {isError ? (
        <ErrorState message="Budgets could not be loaded." />
      ) : (
        <DataTable
          columns={columns}
          rows={positions ?? []}
          keyExtractor={(row) => row.budget_id}
          isLoading={isLoading}
          emptyTitle="No budgets for this year"
          emptyDescription="Set a budget for a cost centre to start tracking it."
        />
      )}
      <HistoryDrawer position={historyOf} onClose={() => setHistoryOf(null)} />
    </Card>
  );
}
