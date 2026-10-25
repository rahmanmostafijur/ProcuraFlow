import { Plus } from "lucide-react";
import { useState } from "react";

import { useApprovalRules, useDeleteRule } from "@/api/approvals";
import { extractErrorMessage } from "@/api/client";
import { useRoles } from "@/api/roles";
import type { ApprovalRule } from "@/api/types";
import { DOCUMENT_TYPE_LABELS } from "@/components/approvals/documentLinks";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { useToast } from "@/components/ui/toast-context";
import { formatCurrency } from "@/lib/utils";

import { RuleFormModal } from "./RuleFormModal";

export function RulesSection() {
  const { showToast } = useToast();
  const { data: rules, isLoading } = useApprovalRules();
  const { data: roles } = useRoles();
  const deleteRule = useDeleteRule();
  const [editing, setEditing] = useState<ApprovalRule | null>(null);
  const [isFormOpen, setFormOpen] = useState(false);
  const [deleting, setDeleting] = useState<ApprovalRule | null>(null);

  const roleName = (id: number) => roles?.find((role) => role.id === id)?.name.replace(/_/g, " ") ?? `Role ${id}`;

  const confirmDelete = async () => {
    if (!deleting) return;
    try {
      await deleteRule.mutateAsync(deleting.id);
      showToast("Rule deleted");
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    } finally {
      setDeleting(null);
    }
  };

  const columns: Column<ApprovalRule>[] = [
    { header: "Applies to", accessor: (row) => DOCUMENT_TYPE_LABELS[row.document_type] },
    { header: "Name", accessor: (row) => <span className="font-medium text-slate-900">{row.name}</span> },
    {
      header: "Amount band",
      accessor: (row) => (
        <span className="tabular-nums">
          {formatCurrency(row.min_amount)} – {row.max_amount === null ? "no limit" : formatCurrency(row.max_amount)}
        </span>
      ),
    },
    {
      header: "Steps",
      accessor: (row) =>
        [...row.steps]
          .sort((a, b) => a.step_order - b.step_order)
          .map((step) => roleName(step.approver_role_id))
          .join(" → "),
    },
    {
      header: "Status",
      accessor: (row) => (
        <Badge status={row.is_active ? "active" : "inactive"}>{row.is_active ? "Active" : "Inactive"}</Badge>
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
            aria-label={`Edit ${row.name}`}
            onClick={() => {
              setEditing(row);
              setFormOpen(true);
            }}
          >
            Edit
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            aria-label={`Delete ${row.name}`}
            onClick={() => setDeleting(row)}
          >
            Delete
          </Button>
        </div>
      ),
    },
  ];

  return (
    <Card>
      <div className="flex items-start justify-between gap-4 border-b border-slate-200 p-4">
        <div>
          <h2 className="text-base font-semibold text-slate-900">Approval rules</h2>
          <p className="text-sm text-slate-500">
            The first matching amount band decides who must approve. Bands for the same kind of document cannot overlap.
          </p>
        </div>
        <Button
          onClick={() => {
            setEditing(null);
            setFormOpen(true);
          }}
        >
          <Plus className="h-4 w-4" /> New rule
        </Button>
      </div>
      <DataTable
        columns={columns}
        rows={rules ?? []}
        keyExtractor={(row) => row.id}
        isLoading={isLoading}
        emptyTitle="No approval rules"
        emptyDescription="Without a rule, the built-in approval permissions apply."
      />
      <RuleFormModal isOpen={isFormOpen} rule={editing} onClose={() => setFormOpen(false)} />
      <ConfirmDialog
        isOpen={deleting !== null}
        title="Delete rule"
        message={`Delete "${deleting?.name ?? ""}"? Documents already waiting keep the steps they were given.`}
        confirmLabel="Delete rule"
        variant="danger"
        isLoading={deleteRule.isPending}
        onConfirm={() => void confirmDelete()}
        onCancel={() => setDeleting(null)}
      />
    </Card>
  );
}
