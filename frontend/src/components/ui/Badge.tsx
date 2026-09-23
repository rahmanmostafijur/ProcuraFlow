import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-slate-100 text-slate-700",
  submitted: "bg-amber-100 text-amber-800",
  approved: "bg-blue-100 text-blue-800",
  ordered: "bg-indigo-100 text-indigo-800",
  partially_received: "bg-purple-100 text-purple-800",
  received: "bg-green-100 text-green-800",
  cancelled: "bg-red-100 text-red-700",
  active: "bg-green-100 text-green-800",
  inactive: "bg-slate-100 text-slate-600",
  pending: "bg-slate-100 text-slate-700",
  on_time: "bg-green-100 text-green-800",
  delayed: "bg-red-100 text-red-700",
  partial: "bg-amber-100 text-amber-800",
};

export function Badge({ status, children }: { status?: string; children: ReactNode }) {
  const colorClass = (status && STATUS_COLORS[status]) ?? "bg-slate-100 text-slate-700";
  return (
    <span className={cn("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium", colorClass)}>
      {children}
    </span>
  );
}
