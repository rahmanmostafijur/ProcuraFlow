import { useDashboardSummary, useMonthlyTrends } from "@/api/dashboard";
import { Card } from "@/components/ui/Card";
import { ThemedBarChart } from "@/components/ui/charts/ThemedBarChart";
import { KpiCard } from "@/components/ui/KpiCard";
import { LoadingState } from "@/components/ui/LoadingState";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAuth } from "@/lib/auth-context";
import { formatCompactMoney, formatMoney, formatNumber } from "@/lib/format";

import { BudgetHealthCard, ExpiringDocumentsCard, RecentActivityCard, WaitingForYouCard } from "./DashboardCards";
import { PipelineStrip } from "./PipelineStrip";

function SpendByMonth() {
  const { data: trends, isLoading } = useMonthlyTrends();
  const points = (trends ?? []).map((point) => ({ month: point.month, total_spend: Number(point.total_spend) }));

  return (
    <Card padding="md" className="lg:col-span-2">
      {isLoading || !trends ? (
        <LoadingState />
      ) : points.length === 0 ? (
        <>
          <h2 className="mb-3 text-title text-text-primary">Committed Spend by Month</h2>
          <p className="py-12 text-center text-sm text-text-secondary">No committed purchase orders yet.</p>
        </>
      ) : (
        <ThemedBarChart
          title="Committed Spend by Month"
          data={points}
          xKey="month"
          series={[{ key: "total_spend", label: "Committed spend" }]}
          formatValue={(value) => formatMoney(value)}
          height={280}
        />
      )}
    </Card>
  );
}

export function DashboardPage() {
  const { hasPermission } = useAuth();
  const { data: summary, isLoading } = useDashboardSummary();
  const { data: trends } = useMonthlyTrends();

  if (isLoading || !summary) return <LoadingState label="Loading dashboard…" />;

  const spendTrend = trends?.map((point) => Number(point.total_spend));
  const committed = trends?.reduce((sum, point) => sum + Number(point.total_spend), 0) ?? 0;

  return (
    <div className="space-y-6">
      <PageHeader title="Dashboard" description="A live snapshot of procurement, inventory, and delivery activity." />

      <PipelineStrip summary={summary} />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Inventory Value"
          value={formatCompactMoney(summary.inventory_value)}
          exactValue={formatMoney(summary.inventory_value)}
        />
        <KpiCard
          label="Committed Spend"
          value={formatCompactMoney(committed)}
          exactValue={formatMoney(committed)}
          trend={spendTrend}
          hint="Last 6 months"
        />
        <KpiCard label="Active Suppliers" value={formatNumber(summary.supplier_count)} />
        <KpiCard label="Low Stock Products" value={formatNumber(summary.low_stock_products)} goodWhen="down" />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <SpendByMonth />
        <WaitingForYouCard />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {hasPermission("budget:read") && <BudgetHealthCard />}
        {hasPermission("supplier:write") && <ExpiringDocumentsCard />}
        {hasPermission("audit:read") && <RecentActivityCard />}
      </div>
    </div>
  );
}
