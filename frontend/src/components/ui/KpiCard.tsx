import { ArrowDownRight, ArrowRight, ArrowUpRight } from "lucide-react";

import { formatPercent } from "@/lib/format";
import { cn } from "@/lib/utils";

import { Card } from "./Card";
import { Skeleton } from "./Skeleton";
import { Sparkline } from "./Sparkline";

interface KpiCardProps {
  label: string;
  /** Already formatted (formatCompactMoney, formatNumber...). The exact figure belongs in `exactValue`. */
  value: string;
  /** Shown as a tooltip and read by screen readers instead of the compact value. */
  exactValue?: string;
  /** Change versus the previous period, in percent points (12.5 means +12.5%). */
  delta?: number;
  /** Which direction is good news. Spend going down is good; approvals going down is not. */
  goodWhen?: "up" | "down";
  deltaLabel?: string;
  trend?: number[];
  hint?: string;
  isLoading?: boolean;
}

function DeltaIndicator({ delta, goodWhen, label }: { delta: number; goodWhen: "up" | "down"; label: string }) {
  const direction = delta > 0 ? "up" : delta < 0 ? "down" : "flat";
  const isGood = direction === "flat" ? null : direction === goodWhen;
  const Icon = direction === "up" ? ArrowUpRight : direction === "down" ? ArrowDownRight : ArrowRight;
  const word = direction === "flat" ? "unchanged" : direction === "up" ? "up" : "down";
  const tone = isGood === null ? "text-text-secondary" : isGood ? "text-success-fg" : "text-danger-fg";
  const tint = isGood === null ? "bg-bg" : isGood ? "bg-success-bg" : "bg-danger-bg";
  const sign = delta > 0 ? "+" : "";
  return (
    <span className={cn("inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-xs font-semibold", tone, tint)}>
      <Icon aria-hidden="true" className="h-3.5 w-3.5" />
      <span aria-hidden="true">
        {sign}
        {formatPercent(delta)}
      </span>
      {/* Spoken form carries the direction and whether it is good, since the colour is not available to everyone. */}
      <span className="sr-only">
        {word} {formatPercent(Math.abs(delta))} {label}
        {isGood === null ? "" : isGood ? ", favourable" : ", unfavourable"}
      </span>
    </span>
  );
}

export function KpiCard({
  label,
  value,
  exactValue,
  delta,
  goodWhen = "up",
  deltaLabel = "versus previous period",
  trend,
  hint,
  isLoading,
}: KpiCardProps) {
  return (
    <Card padding="md" className="flex flex-col gap-2">
      <p className="text-caption uppercase text-text-secondary">{label}</p>
      {isLoading ? (
        <div role="status" aria-busy="true">
          <Skeleton className="h-9 w-32" />
          <span className="sr-only">Loading {label}</span>
        </div>
      ) : (
        <>
          <p data-kpi title={exactValue} className="text-display-md text-text-primary">
            {value}
            {exactValue && <span className="sr-only"> ({exactValue})</span>}
          </p>
          <div className="flex items-end justify-between gap-3">
            <div className="space-y-1">
              {delta !== undefined && <DeltaIndicator delta={delta} goodWhen={goodWhen} label={deltaLabel} />}
              {hint && <p className="text-cell text-text-secondary">{hint}</p>}
            </div>
            {trend && <Sparkline data={trend} ariaLabel={`${label}: ${summariseLabel(trend)}`} />}
          </div>
        </>
      )}
    </Card>
  );
}

function summariseLabel(trend: number[]): string {
  if (trend.length < 2) return "not enough data for a trend";
  const first = trend[0];
  const last = trend[trend.length - 1];
  return `${last > first ? "rising" : last < first ? "falling" : "level"} over ${trend.length} periods`;
}
