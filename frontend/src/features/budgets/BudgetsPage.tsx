import { useState } from "react";

import { useBudgetPositions } from "@/api/budgets";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { useAuth } from "@/lib/auth-context";

import { CostCentresSection } from "./CostCentresSection";
import { PositionsSection } from "./PositionsSection";
import { SetBudgetSection } from "./SetBudgetSection";
import { TransfersSection } from "./TransfersSection";

const FIRST_YEAR = 2000;
const LAST_YEAR = 2100;

export function BudgetsPage() {
  const { hasPermission } = useAuth();
  const [yearText, setYearText] = useState("");
  const year = Number(yearText);
  const isValidYear = Number.isInteger(year) && year >= FIRST_YEAR && year <= LAST_YEAR;
  const fiscalYear = yearText !== "" && isValidYear ? year : undefined;
  const { data: positions, isLoading, isError } = useBudgetPositions(fiscalYear);
  const canManage = hasPermission("budget:manage");
  const canRequestTransfer = hasPermission("budget:request_transfer");

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Budgets</h1>
          <p className="text-sm text-slate-500">
            Spent is what was received or invoiced; committed is what is ordered but not yet spent. Amounts are in the
            company currency.
          </p>
        </div>
        <div className="w-40">
          <Label htmlFor="budget_year">Fiscal year</Label>
          <Input
            id="budget_year"
            inputMode="numeric"
            placeholder="Current"
            value={yearText}
            onChange={(event) => setYearText(event.target.value.trim())}
            error={yearText !== "" && !isValidYear ? `A year from ${FIRST_YEAR} to ${LAST_YEAR}` : undefined}
          />
        </div>
      </div>

      <PositionsSection positions={positions} isLoading={isLoading} isError={isError} />
      {canManage && <SetBudgetSection defaultYear={fiscalYear ?? positions?.[0]?.fiscal_year} />}
      <TransfersSection positions={positions ?? []} canRequest={canRequestTransfer} canDecide={canManage} />
      {canManage && <CostCentresSection />}
    </div>
  );
}
