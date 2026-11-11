import { AlertTriangle, CheckCircle2 } from "lucide-react";

import type { Invoice } from "@/api/supplierInvoices";
import { Card } from "@/components/ui/Card";
import { formatMoney, formatPercent } from "@/lib/format";

import { REASON_LABELS, reasonsForInvoice, reasonsForLine } from "./invoice-rules";

function TotalRow({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  const tone = strong ? "font-semibold text-text-primary" : "text-text-secondary";
  return (
    <tr>
      <td colSpan={5} className={`pt-2 text-right text-sm ${tone}`}>
        {label}
      </td>
      <td className={`pt-2 text-right text-sm tabular-nums ${tone}`}>{value}</td>
    </tr>
  );
}

function LineResult({ invoice, position }: { invoice: Invoice; position: number }) {
  if (invoice.status === "draft") return <span className="text-text-muted">Not matched yet</span>;
  const reasons = reasonsForLine(invoice.exception_reasons, position);
  if (reasons.length === 0) {
    return (
      <span className="inline-flex items-center gap-1 text-success-fg">
        <CheckCircle2 aria-hidden="true" className="h-4 w-4" />
        Matches
      </span>
    );
  }
  return (
    <ul className="space-y-1">
      {reasons.map((reason) => (
        <li key={reason.code} className="flex items-start gap-1 text-attention-fg">
          <AlertTriangle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            <span className="font-medium">{REASON_LABELS[reason.code]}</span>
            <span className="block text-text-secondary">{reason.message}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

export function InvoiceLines({ invoice }: { invoice: Invoice }) {
  const money = (value: string) => formatMoney(value, invoice.currency_code);
  const orderWide = reasonsForInvoice(invoice.exception_reasons);

  return (
    <Card className="p-5 lg:col-span-2">
      <h2 className="mb-1 text-sm font-semibold text-text-primary">Lines</h2>
      {invoice.match_mode && (
        <p className="mb-4 text-xs text-text-secondary">
          {invoice.match_mode === "three_way" ? "Three-way match" : "Two-way match"}
          {invoice.tolerance_percent !== null && ` with ${formatPercent(invoice.tolerance_percent)} tolerance`}
        </p>
      )}
      {orderWide.length > 0 && (
        <ul className="mb-4 space-y-1 rounded-control bg-attention-bg p-3 text-sm text-attention-fg">
          {orderWide.map((reason) => (
            <li key={`${reason.code}-${reason.duplicate_of ?? ""}`}>
              <span className="font-medium">{REASON_LABELS[reason.code]}: </span>
              {reason.message}
            </li>
          ))}
        </ul>
      )}
      {/* A scrollable region needs a tab stop so keyboard users can scroll it (axe: scrollable-region-focusable). */}
      {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
      <div className="overflow-x-auto" role="region" aria-label="Line items" tabIndex={0}>
        <table className="min-w-full divide-y divide-border text-sm">
          <thead>
            <tr className="text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">
              <th className="py-2">Description</th>
              <th className="py-2 text-right">Qty</th>
              <th className="py-2 text-right">Unit price</th>
              <th className="py-2 pl-4">Tax</th>
              <th className="py-2 pl-4">Match result</th>
              <th className="py-2 text-right">Line total</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {invoice.lines.map((line, index) => (
              <tr key={line.id} className="align-top">
                <td className="py-2 text-text-primary">{line.description}</td>
                <td className="py-2 text-right tabular-nums">{line.quantity}</td>
                <td className="py-2 text-right tabular-nums">{money(line.unit_price)}</td>
                <td className="py-2 pl-4 text-text-secondary">
                  {line.tax_name === null ? "—" : `${line.tax_name} ${formatPercent(line.tax_percent)}`}
                </td>
                <td className="py-2 pl-4">
                  <LineResult invoice={invoice} position={index + 1} />
                </td>
                <td className="py-2 text-right tabular-nums">{money(line.line_total)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <TotalRow label="Subtotal" value={money(invoice.subtotal)} />
            <TotalRow label="Tax" value={money(invoice.tax_total)} />
            <TotalRow label={`Total (${invoice.currency_code})`} value={money(invoice.grand_total)} strong />
          </tfoot>
        </table>
      </div>
      {invoice.notes && (
        <div className="mt-4 rounded-control bg-bg p-3 text-sm text-text-secondary">
          <span className="font-medium">Notes: </span>
          {invoice.notes}
        </div>
      )}
    </Card>
  );
}
