import { useState, type FormEvent } from "react";

import { useDecideTransfer, useRequestTransfer, useTransfers } from "@/api/budgets";
import { extractErrorMessage } from "@/api/client";
import type { BudgetPosition, BudgetTransfer } from "@/api/types";
import { DecisionDialog } from "@/components/approvals/DecisionDialog";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Select } from "@/components/ui/Select";
import { useToast } from "@/components/ui/toast-context";
import { formatCurrency, formatDate } from "@/lib/utils";

const AMOUNT_PATTERN = /^\d{1,14}(\.\d{1,4})?$/;

interface TransfersSectionProps {
  positions: BudgetPosition[];
  canRequest: boolean;
  canDecide: boolean;
}

interface Errors {
  from?: string;
  to?: string;
  amount?: string;
  reason?: string;
}

export function TransfersSection({ positions, canRequest, canDecide }: TransfersSectionProps) {
  const { showToast } = useToast();
  const { data: transfers, isLoading } = useTransfers();
  const requestTransfer = useRequestTransfer();
  const decideTransfer = useDecideTransfer();
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const [deciding, setDeciding] = useState<{ transfer: BudgetTransfer; mode: "approve" | "reject" } | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const found: Errors = {};
    if (from === "") found.from = "Choose where the money comes from";
    if (to === "") found.to = "Choose where it goes";
    else if (to === from) found.to = "Choose a different budget";
    if (!AMOUNT_PATTERN.test(amount.trim()) || Number(amount) <= 0)
      found.amount = "An amount above zero, up to 4 decimals";
    if (reason.trim() === "") found.reason = "Say why the money is moving";
    else if (reason.length > 500) found.reason = "At most 500 characters";
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    try {
      await requestTransfer.mutateAsync({
        from_budget_id: Number(from),
        to_budget_id: Number(to),
        amount: amount.trim(),
        reason: reason.trim(),
      });
      setFrom("");
      setTo("");
      setAmount("");
      setReason("");
      showToast("Transfer requested");
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  const decide = async (comment: string) => {
    if (!deciding) return;
    try {
      await decideTransfer.mutateAsync({
        id: deciding.transfer.id,
        approve: deciding.mode === "approve",
        comment: comment || undefined,
      });
      showToast(deciding.mode === "approve" ? "Transfer approved" : "Transfer rejected");
      setDeciding(null);
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  const columns: Column<BudgetTransfer>[] = [
    { header: "From", accessor: (row) => row.from_label },
    { header: "To", accessor: (row) => row.to_label },
    { header: "Amount", accessor: (row) => <span className="tabular-nums">{formatCurrency(row.amount)}</span> },
    {
      header: "Reason",
      accessor: (row) => (
        <div>
          <p>{row.reason}</p>
          {row.decision_comment && <p className="text-xs text-slate-500">“{row.decision_comment}”</p>}
        </div>
      ),
    },
    { header: "Requested by", accessor: (row) => `${row.requested_by.full_name} · ${formatDate(row.created_at)}` },
    { header: "Status", accessor: (row) => <Badge status={row.status}>{row.status}</Badge> },
    {
      header: "",
      accessor: (row) =>
        canDecide && row.status === "pending" ? (
          <div className="flex gap-2">
            <Button
              size="sm"
              aria-label={`Approve transfer ${row.id}`}
              onClick={() => setDeciding({ transfer: row, mode: "approve" })}
            >
              Approve
            </Button>
            <Button
              size="sm"
              variant="danger"
              aria-label={`Reject transfer ${row.id}`}
              onClick={() => setDeciding({ transfer: row, mode: "reject" })}
            >
              Reject
            </Button>
          </div>
        ) : null,
    },
  ];

  const options = positions.map((position) => (
    <option key={position.budget_id} value={position.budget_id}>
      {position.cost_centre_code} — {position.cost_centre_name} ({position.fiscal_year})
    </option>
  ));

  return (
    <Card>
      <div className="border-b border-slate-200 p-4">
        <h2 className="text-base font-semibold text-slate-900">Budget transfers</h2>
        <p className="text-sm text-slate-500">Moving budget between cost centres needs finance approval.</p>
      </div>
      <DataTable
        columns={columns}
        rows={transfers ?? []}
        keyExtractor={(row) => row.id}
        isLoading={isLoading}
        emptyTitle="No transfers"
      />
      {canRequest && (
        <form
          onSubmit={(event) => void submit(event)}
          noValidate
          className="grid gap-3 border-t border-slate-200 p-4 sm:grid-cols-4 sm:items-start"
        >
          <div>
            <Label htmlFor="transfer_from">Move from</Label>
            <Select id="transfer_from" value={from} onChange={(e) => setFrom(e.target.value)} error={errors.from}>
              <option value="">Choose…</option>
              {options}
            </Select>
          </div>
          <div>
            <Label htmlFor="transfer_to">Move to</Label>
            <Select id="transfer_to" value={to} onChange={(e) => setTo(e.target.value)} error={errors.to}>
              <option value="">Choose…</option>
              {options}
            </Select>
          </div>
          <div>
            <Label htmlFor="transfer_amount">Transfer amount</Label>
            <Input
              id="transfer_amount"
              inputMode="decimal"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              error={errors.amount}
            />
          </div>
          <div>
            <Label htmlFor="transfer_reason">Reason for transfer</Label>
            <Input
              id="transfer_reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              error={errors.reason}
            />
          </div>
          <div className="sm:col-span-4 sm:flex sm:justify-end">
            <Button type="submit" disabled={requestTransfer.isPending}>
              Request transfer
            </Button>
          </div>
        </form>
      )}
      <DecisionDialog
        isOpen={deciding !== null}
        mode={deciding?.mode ?? "approve"}
        subject={
          deciding
            ? `${deciding.transfer.from_label} → ${deciding.transfer.to_label}: ${formatCurrency(deciding.transfer.amount)}`
            : ""
        }
        isSubmitting={decideTransfer.isPending}
        onClose={() => setDeciding(null)}
        onSubmit={(comment) => void decide(comment)}
      />
    </Card>
  );
}
