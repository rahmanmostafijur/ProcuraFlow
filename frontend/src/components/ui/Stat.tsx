import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface StatProps {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  className?: string;
}

/** A labelled figure. The value carries data-kpi so it gets tabular numerals. */
export function Stat({ label, value, hint, className }: StatProps) {
  return (
    <dl className={cn("space-y-1", className)}>
      <dt className="text-caption uppercase text-text-secondary">{label}</dt>
      <dd data-kpi className="text-display-sm text-text-primary">
        {value}
      </dd>
      {hint && <dd className="text-cell text-text-secondary">{hint}</dd>}
    </dl>
  );
}
