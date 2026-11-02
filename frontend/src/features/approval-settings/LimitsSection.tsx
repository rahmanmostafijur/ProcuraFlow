import { useState, type FormEvent } from "react";

import { useApprovalLimits, useRemoveLimit, useSetLimit } from "@/api/approvals";
import { extractErrorMessage } from "@/api/client";
import type { ApprovalDocumentType, ApprovalLimit } from "@/api/types";
import { UserPicker } from "@/components/UserPicker";
import { DOCUMENT_TYPE_LABELS } from "@/components/approvals/documentLinks";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Select } from "@/components/ui/Select";
import { useToast } from "@/components/ui/toast-context";
import { formatCurrency } from "@/lib/utils";

const AMOUNT_PATTERN = /^\d{1,14}(\.\d{1,4})?$/;

export function LimitsSection() {
  const { showToast } = useToast();
  const { data: limits, isLoading } = useApprovalLimits();
  const setLimit = useSetLimit();
  const removeLimit = useRemoveLimit();
  const [userId, setUserId] = useState("");
  const [documentType, setDocumentType] = useState<ApprovalDocumentType>("purchase_request");
  const [amount, setAmount] = useState("");
  const [errors, setErrors] = useState<{ user?: string; amount?: string }>({});

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const found: { user?: string; amount?: string } = {};
    if (!/^\d+$/.test(userId) || Number(userId) < 1) found.user = "Choose a person";
    if (!AMOUNT_PATTERN.test(amount.trim())) found.amount = "An amount with up to 4 decimals";
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    try {
      await setLimit.mutateAsync({ user_id: Number(userId), document_type: documentType, max_amount: amount.trim() });
      setUserId("");
      setAmount("");
      showToast("Limit saved");
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  const remove = async (limit: ApprovalLimit) => {
    try {
      await removeLimit.mutateAsync(limit.id);
      showToast("Limit removed");
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  const columns: Column<ApprovalLimit>[] = [
    { header: "User number", accessor: (row) => row.user_id },
    { header: "Applies to", accessor: (row) => DOCUMENT_TYPE_LABELS[row.document_type] },
    {
      header: "Can approve up to",
      accessor: (row) => <span className="tabular-nums">{formatCurrency(row.max_amount)}</span>,
    },
    {
      header: "",
      accessor: (row) => (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          aria-label={`Remove limit for user ${row.user_id} on ${DOCUMENT_TYPE_LABELS[row.document_type]}`}
          onClick={() => void remove(row)}
        >
          Remove
        </Button>
      ),
    },
  ];

  return (
    <Card>
      <div className="border-b border-border p-4">
        <h2 className="text-base font-semibold text-text-primary">Approval limits</h2>
        <p className="text-sm text-text-secondary">
          A person with a limit can approve only up to that amount in the company currency; bigger items go to the next
          step. Setting a limit again replaces the old one.
        </p>
      </div>
      <DataTable
        columns={columns}
        rows={limits ?? []}
        keyExtractor={(row) => row.id}
        isLoading={isLoading}
        emptyTitle="No approval limits"
      />
      <form
        onSubmit={(event) => void submit(event)}
        noValidate
        className="grid gap-3 border-t border-border p-4 sm:grid-cols-4 sm:items-start"
      >
        <UserPicker id="limit_user" label="Person" value={userId} onChange={setUserId} error={errors.user} />
        <div>
          <Label htmlFor="limit_document_type">Limit applies to</Label>
          <Select
            id="limit_document_type"
            value={documentType}
            onChange={(event) => setDocumentType(event.target.value as ApprovalDocumentType)}
          >
            {Object.entries(DOCUMENT_TYPE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor="limit_amount">Limit amount</Label>
          <Input
            id="limit_amount"
            inputMode="decimal"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            error={errors.amount}
          />
        </div>
        <div className="sm:pt-6">
          <Button type="submit" disabled={setLimit.isPending}>
            Set limit
          </Button>
        </div>
      </form>
    </Card>
  );
}
