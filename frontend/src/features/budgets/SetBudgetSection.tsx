import { useState, type FormEvent } from "react";

import { useCostCentres, useSetBudget } from "@/api/budgets";
import { extractErrorMessage } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Select } from "@/components/ui/Select";
import { useToast } from "@/components/ui/toast-context";

const AMOUNT_PATTERN = /^\d{1,14}(\.\d{1,4})?$/;

interface Errors {
  centre?: string;
  year?: string;
  amount?: string;
  reason?: string;
}

export function SetBudgetSection({ defaultYear }: { defaultYear: number | undefined }) {
  const { showToast } = useToast();
  const { data: costCentres } = useCostCentres(true);
  const setBudget = useSetBudget();
  const [centre, setCentre] = useState("");
  const [typedYear, setYear] = useState<string | null>(null);
  const year = typedYear ?? (defaultYear === undefined ? "" : String(defaultYear));
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [errors, setErrors] = useState<Errors>({});

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const found: Errors = {};
    const yearNumber = Number(year);
    if (centre === "") found.centre = "Choose a cost centre";
    if (!Number.isInteger(yearNumber) || yearNumber < 2000 || yearNumber > 2100)
      found.year = "A year from 2000 to 2100";
    if (!AMOUNT_PATTERN.test(amount.trim())) found.amount = "An amount with up to 4 decimals";
    if (reason.length > 500) found.reason = "At most 500 characters";
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    try {
      await setBudget.mutateAsync({
        cost_centre_id: Number(centre),
        fiscal_year: yearNumber,
        amount: amount.trim(),
        reason: reason.trim() === "" ? undefined : reason.trim(),
      });
      setAmount("");
      setReason("");
      showToast("Budget saved");
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  return (
    <Card>
      <div className="border-b border-slate-200 p-4">
        <h2 className="text-base font-semibold text-slate-900">Set a budget</h2>
        <p className="text-sm text-slate-500">
          Setting a budget again for the same year replaces the amount and is recorded in its history.
        </p>
      </div>
      <form
        onSubmit={(event) => void submit(event)}
        noValidate
        className="grid gap-3 p-4 sm:grid-cols-4 sm:items-start"
      >
        <div>
          <Label htmlFor="set_budget_centre">Cost centre to budget</Label>
          <Select
            id="set_budget_centre"
            value={centre}
            onChange={(e) => setCentre(e.target.value)}
            error={errors.centre}
          >
            <option value="">Choose…</option>
            {costCentres?.map((item) => (
              <option key={item.id} value={item.id}>
                {item.code} — {item.name}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor="set_budget_year">Budget year</Label>
          <Input
            id="set_budget_year"
            inputMode="numeric"
            value={year}
            onChange={(e) => setYear(e.target.value)}
            error={errors.year}
          />
        </div>
        <div>
          <Label htmlFor="set_budget_amount">Budget amount</Label>
          <Input
            id="set_budget_amount"
            inputMode="decimal"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            error={errors.amount}
          />
        </div>
        <div>
          <Label htmlFor="set_budget_reason">Reason (optional)</Label>
          <Input
            id="set_budget_reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            error={errors.reason}
          />
        </div>
        <div className="sm:col-span-4 sm:flex sm:justify-end">
          <Button type="submit" disabled={setBudget.isPending}>
            Save budget
          </Button>
        </div>
      </form>
    </Card>
  );
}
