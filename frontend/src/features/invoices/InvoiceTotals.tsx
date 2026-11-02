import type { InvoiceListTotals } from "@/api/supplierInvoices";
import { Card } from "@/components/ui/Card";
import { formatMoney, formatNumber } from "@/lib/format";

interface InvoiceTotalsProps {
  totals: InvoiceListTotals;
}

/** Figures for everything the list's filters match, not just the visible page. */
export function InvoiceTotals({ totals }: InvoiceTotalsProps) {
  const tiles = [
    { label: "Need attention", value: formatNumber(totals.needing_attention) },
    { label: "Payables outstanding", value: formatMoney(totals.payables_outstanding) },
    { label: "Payables overdue", value: formatMoney(totals.payables_overdue) },
  ];
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      {tiles.map((tile) => (
        <Card key={tile.label} padding="md">
          <p className="text-sm text-text-secondary">{tile.label}</p>
          <p className="mt-1 text-title tabular-nums text-text-primary">{tile.value}</p>
        </Card>
      ))}
    </div>
  );
}
