import type { ReactNode } from "react";

import { Card } from "@/components/ui/Card";

export interface SummaryRow {
  label: string;
  value: ReactNode;
  /** Amounts: right aligned with tabular figures. */
  numeric?: boolean;
}

interface SummaryListProps {
  title?: string;
  rows: SummaryRow[];
  /** Free text shown under the rows, such as the notes of a document. */
  footer?: ReactNode;
}

/** The "summary panel" of a document page: who, when and how much, as label/value pairs. */
export function SummaryList({ title = "Details", rows, footer }: SummaryListProps) {
  return (
    <Card padding="md">
      <h2 className="mb-4 text-title text-text-primary">{title}</h2>
      <dl className="space-y-3 text-sm">
        {rows.map((row) => (
          <div key={row.label} className="flex justify-between gap-3">
            <dt className="text-text-secondary">{row.label}</dt>
            <dd className={row.numeric ? "text-right font-medium tabular-nums text-text-primary" : "text-text-primary"}>
              {row.value}
            </dd>
          </div>
        ))}
      </dl>
      {footer && <div className="mt-4 border-t border-border pt-3 text-sm text-text-secondary">{footer}</div>}
    </Card>
  );
}
