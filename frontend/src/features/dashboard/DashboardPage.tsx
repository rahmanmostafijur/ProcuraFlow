import { AlertTriangle, Boxes, ClipboardList, DollarSign, Truck, Users as UsersIcon } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { useDashboardSummary, useMonthlyTrends, useRecentActivity } from "@/api/dashboard";
import { Card } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/LoadingState";
import { formatCurrency, formatDateTime } from "@/lib/utils";

function StatCard({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Boxes;
  label: string;
  value: string | number;
}) {
  return (
    <Card className="flex items-center gap-4 p-5">
      <div className="flex h-10 w-10 items-center justify-center rounded-md bg-brand-50 text-brand-600">
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
        <p className="text-xl font-semibold text-slate-900">{value}</p>
      </div>
    </Card>
  );
}

export function DashboardPage() {
  const { data: summary, isLoading: summaryLoading } = useDashboardSummary();
  const { data: trends, isLoading: trendsLoading } = useMonthlyTrends();
  const { data: activity, isLoading: activityLoading } = useRecentActivity();

  if (summaryLoading || !summary) {
    return <LoadingState label="Loading dashboard…" />;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Dashboard</h1>
        <p className="text-sm text-slate-500">A live snapshot of procurement, inventory, and delivery activity.</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={ClipboardList} label="Purchase Orders" value={summary.total_purchase_orders} />
        <StatCard icon={AlertTriangle} label="Pending Orders" value={summary.pending_orders} />
        <StatCard icon={Truck} label="Upcoming Deliveries" value={summary.upcoming_deliveries} />
        <StatCard icon={UsersIcon} label="Active Suppliers" value={summary.supplier_count} />
        <StatCard icon={DollarSign} label="Inventory Value" value={formatCurrency(summary.inventory_value)} />
        <StatCard icon={Boxes} label="Low Stock Products" value={summary.low_stock_products} />
        <StatCard icon={ClipboardList} label="Completed Orders" value={summary.completed_orders} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="p-5 lg:col-span-2">
          <h2 className="mb-4 text-sm font-semibold text-slate-900">Committed Spend by Month</h2>
          {trendsLoading || !trends ? (
            <LoadingState />
          ) : trends.length === 0 ? (
            <p className="py-12 text-center text-sm text-slate-500">No committed purchase orders yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={trends}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="month" tick={{ fontSize: 12 }} stroke="#94a3b8" />
                <YAxis tick={{ fontSize: 12 }} stroke="#94a3b8" />
                <Tooltip formatter={(value: number) => formatCurrency(value)} />
                <Bar dataKey="total_spend" name="Committed spend" fill="#3660f5" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>

        <Card className="p-5">
          <h2 className="mb-4 text-sm font-semibold text-slate-900">Recent Activity</h2>
          {activityLoading || !activity ? (
            <LoadingState />
          ) : activity.length === 0 ? (
            <p className="py-12 text-center text-sm text-slate-500">No recent activity.</p>
          ) : (
            <ul className="space-y-3">
              {activity.map((item) => (
                <li key={item.id} className="text-sm">
                  <p className="text-slate-800">
                    <span className="font-medium">{item.user_name ?? "System"}</span>{" "}
                    {item.action.replace(/_/g, " ")}
                  </p>
                  <p className="text-xs text-slate-400">{formatDateTime(item.created_at)}</p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
