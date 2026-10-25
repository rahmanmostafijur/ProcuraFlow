import { useState, type FormEvent } from "react";

import { useCreateDelegation, useDelegations, useRevokeDelegation } from "@/api/approvals";
import { extractErrorMessage } from "@/api/client";
import type { Delegation } from "@/api/types";
import { UserPicker } from "@/components/UserPicker";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { useToast } from "@/components/ui/toast-context";
import { formatDate } from "@/lib/utils";

interface FormErrors {
  delegate?: string;
  starts?: string;
  ends?: string;
}

function validate(delegate: string, starts: string, ends: string): FormErrors {
  const errors: FormErrors = {};
  if (!/^\d+$/.test(delegate) || Number(delegate) < 1) errors.delegate = "Choose who covers for you";
  if (starts === "") errors.starts = "Choose a start date";
  if (ends === "") errors.ends = "Choose an end date";
  else if (starts !== "" && ends < starts) errors.ends = "The end date cannot be before the start date";
  return errors;
}

function statusOf(delegation: Delegation, today: string): { key: string; label: string } {
  if (delegation.revoked_at) return { key: "cancelled", label: "Revoked" };
  if (delegation.ends_on < today) return { key: "inactive", label: "Ended" };
  if (delegation.starts_on > today) return { key: "pending", label: "Scheduled" };
  return { key: "active", label: "Active" };
}

export function DelegationsSection() {
  const { showToast } = useToast();
  const { data: delegations, isLoading } = useDelegations();
  const create = useCreateDelegation();
  const revoke = useRevokeDelegation();
  const [delegate, setDelegate] = useState("");
  const [starts, setStarts] = useState("");
  const [ends, setEnds] = useState("");
  const [errors, setErrors] = useState<FormErrors>({});
  const today = new Date().toISOString().slice(0, 10);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const found = validate(delegate, starts, ends);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    try {
      await create.mutateAsync({ delegate_id: Number(delegate), starts_on: starts, ends_on: ends });
      setDelegate("");
      setStarts("");
      setEnds("");
      showToast("Delegation created");
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  const handleRevoke = async (delegation: Delegation) => {
    try {
      await revoke.mutateAsync(delegation.id);
      showToast("Delegation revoked");
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  const columns: Column<Delegation>[] = [
    { header: "From", accessor: (row) => row.delegator.full_name },
    { header: "Covered by", accessor: (row) => row.delegate.full_name },
    { header: "Starts", accessor: (row) => formatDate(row.starts_on) },
    { header: "Ends", accessor: (row) => formatDate(row.ends_on) },
    {
      header: "Status",
      accessor: (row) => {
        const status = statusOf(row, today);
        return <Badge status={status.key}>{status.label}</Badge>;
      },
    },
    {
      header: "",
      accessor: (row) =>
        row.revoked_at || row.ends_on < today ? null : (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            aria-label={`Revoke delegation to ${row.delegate.full_name}`}
            onClick={() => void handleRevoke(row)}
          >
            Revoke
          </Button>
        ),
    },
  ];

  return (
    <Card>
      <div className="border-b border-slate-200 p-4">
        <h2 className="text-base font-semibold text-slate-900">While I&apos;m away</h2>
        <p className="text-sm text-slate-500">
          Let a colleague decide what is waiting for you between two dates. Every decision they make for you is recorded
          as made on your behalf.
        </p>
      </div>
      <DataTable
        columns={columns}
        rows={delegations ?? []}
        keyExtractor={(row) => row.id}
        isLoading={isLoading}
        emptyTitle="No delegations"
      />
      <form
        onSubmit={(event) => void submit(event)}
        noValidate
        className="grid gap-3 border-t border-slate-200 p-4 sm:grid-cols-4 sm:items-start"
      >
        <UserPicker
          id="delegate_id"
          label="Covered by"
          value={delegate}
          onChange={setDelegate}
          error={errors.delegate}
        />
        <div>
          <Label htmlFor="delegation_starts">Away from</Label>
          <Input
            id="delegation_starts"
            type="date"
            value={starts}
            onChange={(e) => setStarts(e.target.value)}
            error={errors.starts}
          />
        </div>
        <div>
          <Label htmlFor="delegation_ends">Back on</Label>
          <Input
            id="delegation_ends"
            type="date"
            value={ends}
            onChange={(e) => setEnds(e.target.value)}
            error={errors.ends}
          />
        </div>
        <div className="sm:pt-6">
          <Button type="submit" disabled={create.isPending}>
            Delegate approvals
          </Button>
        </div>
      </form>
    </Card>
  );
}
