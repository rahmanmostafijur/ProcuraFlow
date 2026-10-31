import { useState, type FormEvent } from "react";

import { extractErrorMessage } from "@/api/client";
import { useRequestBankChange, type BankChangeInput } from "@/api/supplierBank";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { useToast } from "@/components/ui/toast-context";

const EMPTY = {
  bank_account_name: "",
  bank_country: "",
  iban: "",
  bic: "",
  bank_account_number: "",
  routing_number: "",
};

type FormState = typeof EMPTY;

const FIELDS: { name: keyof FormState; label: string }[] = [
  { name: "bank_account_name", label: "Account holder" },
  { name: "bank_country", label: "Bank country (two letters)" },
  { name: "iban", label: "IBAN" },
  { name: "bic", label: "BIC" },
  { name: "bank_account_number", label: "Account number" },
  { name: "routing_number", label: "Routing number" },
];

/** Only fills in what the API needs; it checks the identifiers again and its refusal is shown as typed. */
export function BankChangeForm({ supplierId }: { supplierId: number }) {
  const { showToast } = useToast();
  const request = useRequestBankChange(supplierId);
  const [values, setValues] = useState<FormState>(EMPTY);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!values.bank_account_name.trim() || values.bank_country.trim().length !== 2) {
      setError("Enter the account holder and a two-letter bank country");
      return;
    }
    if (!values.iban.trim() && !values.bank_account_number.trim()) {
      setError("Give an IBAN or a bank account number");
      return;
    }
    setError(null);
    const payload: BankChangeInput = {
      bank_account_name: values.bank_account_name.trim(),
      bank_country: values.bank_country.trim().toUpperCase(),
      iban: values.iban.trim() || undefined,
      bic: values.bic.trim() || undefined,
      bank_account_number: values.bank_account_number.trim() || undefined,
      routing_number: values.routing_number.trim() || undefined,
    };
    try {
      await request.mutateAsync(payload);
      setValues(EMPTY);
      showToast("Change requested. Someone else must approve it.");
    } catch (failure) {
      setError(extractErrorMessage(failure));
    }
  };

  return (
    <form onSubmit={(event) => void submit(event)} className="space-y-3" aria-label="Request a bank details change">
      <h3 className="text-sm font-semibold text-slate-800">Request a change</h3>
      <div className="grid gap-3 sm:grid-cols-2">
        {FIELDS.map((field) => (
          <div key={field.name}>
            <Label htmlFor={`bank-${field.name}`}>{field.label}</Label>
            <Input
              id={`bank-${field.name}`}
              value={values[field.name]}
              onChange={(event) => setValues({ ...values, [field.name]: event.target.value })}
            />
          </div>
        ))}
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}
      <Button type="submit" disabled={request.isPending}>
        {request.isPending ? "Sending…" : "Request change"}
      </Button>
    </form>
  );
}
