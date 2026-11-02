import { useInvoicePayments, type Invoice } from "@/api/supplierInvoices";
import { Card } from "@/components/ui/Card";
import { formatDate, formatMoney } from "@/lib/format";

import { PAYMENT_METHOD_LABELS } from "./invoice-rules";

export function InvoicePayments({ invoice }: { invoice: Invoice }) {
  const { data: payments, isLoading, isError } = useInvoicePayments(invoice.id);

  return (
    <Card className="p-5">
      <h2 className="mb-2 text-sm font-semibold text-text-primary">Payments</h2>
      {isLoading && <p className="text-sm text-text-secondary">Loading payments…</p>}
      {isError && <p className="text-sm text-danger-fg">The payments could not be loaded.</p>}
      {payments && payments.length === 0 && <p className="text-sm text-text-secondary">Nothing has been paid yet.</p>}
      <ul className="divide-y divide-border">
        {payments?.map((payment) => (
          <li key={payment.id} className="flex items-start justify-between gap-3 py-3 text-sm">
            <div>
              <p className="font-medium text-text-primary">{PAYMENT_METHOD_LABELS[payment.method]}</p>
              <p className="text-text-secondary">
                {formatDate(payment.paid_on)} · {payment.creator.full_name}
                {payment.reference && ` · ${payment.reference}`}
              </p>
            </div>
            <span className="tabular-nums text-text-primary">{formatMoney(payment.amount, payment.currency_code)}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
