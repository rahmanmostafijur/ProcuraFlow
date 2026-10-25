import { useState, type FormEvent } from "react";

import { useCostCentres, useSaveCostCentre } from "@/api/budgets";
import { extractErrorMessage } from "@/api/client";
import type { CostCentre } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { useToast } from "@/components/ui/toast-context";

interface Errors {
  code?: string;
  name?: string;
}

export function CostCentresSection() {
  const { showToast } = useToast();
  const { data: centres, isLoading } = useCostCentres();
  const save = useSaveCostCentre();
  const [editing, setEditing] = useState<CostCentre | null>(null);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [errors, setErrors] = useState<Errors>({});

  const reset = () => {
    setEditing(null);
    setCode("");
    setName("");
    setErrors({});
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const found: Errors = {};
    if (!editing && (code.trim() === "" || code.trim().length > 20)) found.code = "A code of 1 to 20 characters";
    if (name.trim() === "" || name.trim().length > 150) found.name = "A name of 1 to 150 characters";
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    try {
      if (editing) await save.mutateAsync({ id: editing.id, name: name.trim() });
      else await save.mutateAsync({ code: code.trim(), name: name.trim() });
      showToast(editing ? "Cost centre updated" : "Cost centre created");
      reset();
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  const toggle = async (centre: CostCentre) => {
    try {
      await save.mutateAsync({ id: centre.id, is_active: !centre.is_active });
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  const columns: Column<CostCentre>[] = [
    { header: "Code", accessor: (row) => <span className="font-medium text-slate-900">{row.code}</span> },
    { header: "Name", accessor: (row) => row.name },
    {
      header: "Status",
      accessor: (row) => (
        <Badge status={row.is_active ? "active" : "inactive"}>{row.is_active ? "Active" : "Retired"}</Badge>
      ),
    },
    {
      header: "",
      accessor: (row) => (
        <div className="flex gap-1">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            aria-label={`Edit ${row.code}`}
            onClick={() => {
              setEditing(row);
              setName(row.name);
              setCode(row.code);
              setErrors({});
            }}
          >
            Edit
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            aria-label={`${row.is_active ? "Retire" : "Reactivate"} ${row.code}`}
            onClick={() => void toggle(row)}
          >
            {row.is_active ? "Retire" : "Reactivate"}
          </Button>
        </div>
      ),
    },
  ];

  return (
    <Card>
      <div className="border-b border-slate-200 p-4">
        <h2 className="text-base font-semibold text-slate-900">Cost centres</h2>
        <p className="text-sm text-slate-500">A retired cost centre keeps its history but can no longer be chosen.</p>
      </div>
      <DataTable
        columns={columns}
        rows={centres ?? []}
        keyExtractor={(row) => row.id}
        isLoading={isLoading}
        emptyTitle="No cost centres"
      />
      <form
        onSubmit={(event) => void submit(event)}
        noValidate
        className="grid gap-3 border-t border-slate-200 p-4 sm:grid-cols-3 sm:items-start"
      >
        <div>
          <Label htmlFor="cost_centre_code">Cost centre code</Label>
          <Input
            id="cost_centre_code"
            value={code}
            disabled={editing !== null}
            onChange={(e) => setCode(e.target.value)}
            error={errors.code}
          />
        </div>
        <div>
          <Label htmlFor="cost_centre_name">Cost centre name</Label>
          <Input id="cost_centre_name" value={name} onChange={(e) => setName(e.target.value)} error={errors.name} />
        </div>
        <div className="flex gap-2 sm:pt-6">
          <Button type="submit" disabled={save.isPending}>
            {editing ? "Save cost centre" : "Add cost centre"}
          </Button>
          {editing && (
            <Button type="button" variant="secondary" onClick={reset}>
              Cancel editing
            </Button>
          )}
        </div>
      </form>
    </Card>
  );
}
