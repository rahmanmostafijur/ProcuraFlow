import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useMemo } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { extractErrorMessage } from "@/api/client";
import { useCreatePaymentRun, type PaymentRunMethod } from "@/api/paymentRuns";
import { useInvoices, type InvoiceSummary } from "@/api/supplierInvoices";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Label } from "@/components/ui/Label";
import { LoadingState } from "@/components/ui/LoadingState";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";
import { useToast } from "@/components/ui/toast-context";
import { formatDate, formatMoney } from "@/lib/format";
import { currencyDecimals, sumAmounts } from "@/lib/money";
import { useUnsavedChangesWarning } from "@/lib/use-unsaved-changes";

const FORM_ID = "new-payment-run-form";
const MAX_INVOICES = 500;
const LIST_SIZE = 100;
const METHOD_LABELS: Record<PaymentRunMethod, string> = {
  bank_transfer: "Bank transfer",
  card: "Card",
  cheque: "Cheque",
};

interface FormValues {
  method: PaymentRunMethod;
  invoice_ids: number[];
}

function buildSchema(currencyById: ReadonlyMap<number, string>) {
  return z.object({
    method: z.enum(["bank_transfer", "card", "cheque"]),
    invoice_ids: z
      .array(z.number())
      .min(1, "Select at least one invoice")
      .max(MAX_INVOICES, `A run holds at most ${MAX_INVOICES} invoices`)
      .refine((ids) => new Set(ids.map((id) => currencyById.get(id))).size <= 1, {
        message: "A payment run pays one currency; select invoices in a single currency",
      }),
  });
}

/** Totals per currency, in the order the currencies first appear. */
function totalsByCurrency(invoices: readonly InvoiceSummary[]): { currency: string; total: string }[] {
  const groups = new Map<string, string[]>();
  for (const invoice of invoices) {
    groups.set(invoice.currency_code, [...(groups.get(invoice.currency_code) ?? []), invoice.open_amount]);
  }
  return [...groups].map(([currency, amounts]) => ({
    currency,
    total: sumAmounts(amounts, currencyDecimals(currency)),
  }));
}

export function NewPaymentRunModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const { showToast } = useToast();
  const create = useCreatePaymentRun();
  const { data, isLoading, isError, error, refetch } = useInvoices({
    page: 1,
    page_size: LIST_SIZE,
    status: "approved",
  });
  const payable = useMemo(() => (data?.items ?? []).filter((invoice) => Number(invoice.open_amount) > 0), [data]);
  const resolver = useMemo(
    () => zodResolver(buildSchema(new Map(payable.map((invoice) => [invoice.id, invoice.currency_code])))),
    [payable],
  );
  const {
    register,
    handleSubmit,
    reset,
    control,
    setValue,
    formState: { errors, isDirty, isSubmitted },
  } = useForm<FormValues>({ resolver, defaultValues: { method: "bank_transfer", invoice_ids: [] } });
  const selectedIds = useWatch({ control, name: "invoice_ids" });
  useUnsavedChangesWarning(isOpen && isDirty);

  useEffect(() => {
    if (isOpen) reset({ method: "bank_transfer", invoice_ids: [] });
  }, [isOpen, reset]);

  const selected = payable.filter((invoice) => selectedIds.includes(invoice.id));
  const allSelected = payable.length > 0 && selected.length === payable.length;

  const setSelection = (ids: number[]) =>
    setValue("invoice_ids", ids, { shouldDirty: true, shouldValidate: isSubmitted });
  const toggle = (id: number) =>
    setSelection(selectedIds.includes(id) ? selectedIds.filter((item) => item !== id) : [...selectedIds, id]);

  const submit = handleSubmit(async (values) => {
    try {
      const run = await create.mutateAsync(values);
      showToast(`Payment run ${run.number} created`);
      onClose();
    } catch (failure) {
      showToast(extractErrorMessage(failure), "error");
    }
  });

  const footer = (
    <>
      <Button variant="secondary" type="button" onClick={onClose}>
        Cancel
      </Button>
      <Button type="submit" form={FORM_ID} disabled={create.isPending || payable.length === 0}>
        {create.isPending ? "Creating…" : "Create payment run"}
      </Button>
    </>
  );

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="New payment run"
      description="Group approved invoices of one currency into a draft run. A second person releases it."
      size="lg"
      footer={footer}
      closeOnBackdrop={!isDirty}
    >
      {isLoading ? (
        <LoadingState label="Loading payable invoices…" />
      ) : isError ? (
        <ErrorState
          message={extractErrorMessage(error)}
          action={
            <Button variant="secondary" onClick={() => void refetch()}>
              Try again
            </Button>
          }
        />
      ) : payable.length === 0 ? (
        <EmptyState
          title="No payable invoices"
          description="Approved invoices with an open amount appear here once they are ready to pay."
        />
      ) : (
        <form id={FORM_ID} noValidate onSubmit={(event) => void submit(event)} className="space-y-4">
          <div className="max-w-xs">
            <Label htmlFor="payment_run_method">Payment method</Label>
            <Select id="payment_run_method" {...register("method")}>
              {Object.entries(METHOD_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </div>
          <div className="max-h-80 overflow-y-auto rounded-control border border-border">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 bg-bg text-xs uppercase text-text-secondary">
                <tr>
                  <th className="w-10 px-3 py-2">
                    <Checkbox
                      aria-label="Select all invoices"
                      checked={allSelected}
                      indeterminate={selected.length > 0 && !allSelected}
                      onChange={() => setSelection(allSelected ? [] : payable.map((invoice) => invoice.id))}
                    />
                  </th>
                  <th className="px-3 py-2">Supplier</th>
                  <th className="px-3 py-2">Invoice</th>
                  <th className="px-3 py-2">Due</th>
                  <th className="px-3 py-2 text-right">Open amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border bg-surface">
                {payable.map((invoice) => (
                  <tr key={invoice.id}>
                    <td className="px-3 py-2">
                      <Checkbox
                        aria-label={`Select invoice ${invoice.invoice_number}`}
                        checked={selectedIds.includes(invoice.id)}
                        onChange={() => toggle(invoice.id)}
                      />
                    </td>
                    <td className="px-3 py-2">{invoice.supplier.name}</td>
                    <td className="px-3 py-2">{invoice.invoice_number}</td>
                    <td className="px-3 py-2">{formatDate(invoice.due_date)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {formatMoney(invoice.open_amount, invoice.currency_code)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {errors.invoice_ids && (
            <p role="alert" className="text-sm text-danger-fg">
              {errors.invoice_ids.message}
            </p>
          )}
          <dl className="flex flex-wrap items-baseline justify-end gap-x-6 gap-y-1 text-sm" aria-live="polite">
            <dt className="text-text-secondary">{selected.length} selected</dt>
            {totalsByCurrency(selected).map(({ currency, total }) => (
              <dd key={currency} className="font-semibold tabular-nums text-text-primary">
                {formatMoney(total, currency)}
              </dd>
            ))}
          </dl>
          {data && data.total > payable.length && (
            <p className="text-xs text-text-secondary">
              Showing the first {LIST_SIZE} approved invoices; create this run, then make another for the rest.
            </p>
          )}
        </form>
      )}
    </Modal>
  );
}
