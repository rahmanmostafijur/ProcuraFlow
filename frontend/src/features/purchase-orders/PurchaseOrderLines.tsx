import type { POItem, PurchaseOrder } from "@/api/types";
import { Card } from "@/components/ui/Card";
import { currencyDecimals, sumAmounts } from "@/lib/money";
import { formatCurrency } from "@/lib/utils";

interface TaxBreakdownRow {
  key: string;
  label: string;
  amount: string;
}

function taxLabel(item: POItem): string {
  if (item.reverse_charge) return `${item.tax_name ?? "Reverse charge"} (buyer accounts for tax)`;
  return `${item.tax_name ?? "Tax"}${item.tax_inclusive ? " (included)" : ""}`;
}

/** One row per tax rate used on the order, so the document shows how much of each tax it carries. */
function taxBreakdown(po: PurchaseOrder): TaxBreakdownRow[] {
  const decimals = currencyDecimals(po.currency_code);
  const groups = new Map<string, { label: string; amounts: string[] }>();
  for (const item of po.items) {
    if (item.tax_name === null) continue;
    const key = `${item.tax_name}|${item.tax_percent}|${item.tax_inclusive}|${item.reverse_charge}`;
    const group = groups.get(key) ?? { label: taxLabel(item), amounts: [] };
    group.amounts.push(item.line_tax);
    groups.set(key, group);
  }
  return [...groups.entries()].map(([key, group]) => ({
    key,
    label: group.label,
    amount: sumAmounts(group.amounts, decimals),
  }));
}

function TotalRow({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <tr>
      <td
        colSpan={5}
        className={`pt-2 text-right text-sm ${strong ? "font-semibold text-text-primary" : "text-text-secondary"}`}
      >
        {label}
      </td>
      <td
        className={`pt-2 text-right text-sm tabular-nums ${strong ? "font-semibold text-text-primary" : "text-text-secondary"}`}
      >
        {value}
      </td>
    </tr>
  );
}

export function PurchaseOrderLines({ po }: { po: PurchaseOrder }) {
  const money = (value: string) => formatCurrency(value, po.currency_code);
  const isLocked = po.exchange_rate !== null && po.base_grand_total !== null;

  return (
    <Card className="p-5 lg:col-span-2">
      <h2 className="mb-4 text-sm font-semibold text-text-primary">Line Items</h2>
      {/* A scrollable region needs a tab stop so keyboard users can scroll it (axe: scrollable-region-focusable). */}
      {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
      <div className="overflow-x-auto" role="region" aria-label="Line items" tabIndex={0}>
        <table className="min-w-full divide-y divide-border text-sm">
          <thead>
            <tr className="text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">
              <th className="py-2">Product ID</th>
              <th className="py-2">Quantity</th>
              <th className="py-2">Received</th>
              <th className="py-2 text-right">Unit Price</th>
              <th className="py-2 pl-4">Tax</th>
              <th className="py-2 text-right">Line Total</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {po.items.map((item) => (
              <tr key={item.id}>
                <td className="py-2">{item.product_id}</td>
                <td className="py-2 tabular-nums">{item.quantity}</td>
                <td className="py-2 tabular-nums">{item.received_quantity}</td>
                <td className="py-2 text-right tabular-nums">{money(item.unit_price)}</td>
                <td className="py-2 pl-4 text-text-secondary">
                  {item.tax_name === null ? "—" : `${item.tax_name} ${Number(item.tax_percent)}%`}
                </td>
                <td className="py-2 text-right tabular-nums">{money(item.line_total)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <TotalRow label="Subtotal" value={money(po.subtotal)} />
            {taxBreakdown(po).map((row) => (
              <TotalRow key={row.key} label={row.label} value={money(row.amount)} />
            ))}
            <TotalRow label={`Total (${po.currency_code})`} value={money(po.grand_total)} strong />
            {isLocked && po.base_grand_total !== null && (
              <TotalRow
                label={`Total in base currency at the approved rate of ${Number(po.exchange_rate)}`}
                value={formatCurrency(po.base_grand_total)}
              />
            )}
          </tfoot>
        </table>
      </div>
      {po.notes && (
        <div className="mt-4 rounded-control bg-bg p-3 text-sm text-text-secondary">
          <span className="font-medium text-text-secondary">Notes: </span>
          {po.notes}
        </div>
      )}
    </Card>
  );
}
