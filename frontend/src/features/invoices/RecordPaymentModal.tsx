import { useState } from "react";

import type { Invoice, PaymentInput, PaymentMethod } from "@/api/supplierInvoices";
import { Button } from "@/components/ui/Button";
import { FormField } from "@/components/ui/FormField";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";
import { formatMoney } from "@/lib/format";

import { PAYMENT_METHOD_LABELS } from "./invoice-rules";

interface RecordPaymentModalProps {
  isOpen: boolean;
  invoice: Invoice;
  isSubmitting?: boolean;
  onClose: () => void;
  onSubmit: (input: PaymentInput) => void;
}

const POSITIVE_DECIMAL = /^\d+(\.\d{1,4})?$/;

export function RecordPaymentModal(props: RecordPaymentModalProps) {
  return (
    <Modal isOpen={props.isOpen} onClose={props.onClose} title="Record payment" size="sm">
      <PaymentForm {...props} />
    </Modal>
  );
}

// Mounted only while open, so each opening starts from the open amount.
function PaymentForm({ invoice, isSubmitting, onClose, onSubmit }: RecordPaymentModalProps) {
  const [amount, setAmount] = useState(invoice.open_amount);
  const [method, setMethod] = useState<PaymentMethod>("bank_transfer");
  const [paidOn, setPaidOn] = useState("");
  const [reference, setReference] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = () => {
    const value = amount.trim();
    if (!POSITIVE_DECIMAL.test(value) || Number(value) <= 0) {
      setError("Enter an amount above zero, with at most four decimals");
      return;
    }
    onSubmit({ amount: value, method, paid_on: paidOn || null, reference: reference.trim() || null });
  };

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
      className="space-y-4"
    >
      <p className="text-sm text-text-secondary">
        {invoice.invoice_number} · still open {formatMoney(invoice.open_amount, invoice.currency_code)}. A payment can
        never exceed what is open.
      </p>
      <FormField label={`Amount (${invoice.currency_code})`} required error={error ?? undefined}>
        <Input inputMode="decimal" value={amount} onChange={(event) => setAmount(event.target.value)} />
      </FormField>
      <FormField label="Method" required>
        <Select value={method} onChange={(event) => setMethod(event.target.value as PaymentMethod)}>
          {Object.entries(PAYMENT_METHOD_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </Select>
      </FormField>
      <FormField label="Paid on" hint="Leave empty for today. It cannot be in the future.">
        <Input type="date" value={paidOn} onChange={(event) => setPaidOn(event.target.value)} />
      </FormField>
      <FormField label="Reference">
        <Input maxLength={100} value={reference} onChange={(event) => setReference(event.target.value)} />
      </FormField>
      <div className="flex justify-end gap-3">
        <Button type="button" variant="secondary" onClick={onClose} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Please wait…" : "Record payment"}
        </Button>
      </div>
    </form>
  );
}
