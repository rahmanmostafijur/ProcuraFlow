import { useState } from "react";
import { Link } from "react-router-dom";

import { useApprovalQueue, useDecide } from "@/api/approvals";
import { extractErrorMessage } from "@/api/client";
import type { QueueItem } from "@/api/types";
import { DecisionDialog } from "@/components/approvals/DecisionDialog";
import { DOCUMENT_TYPE_LABELS, documentLink } from "@/components/approvals/documentLinks";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { ErrorState } from "@/components/ui/ErrorState";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { useToast } from "@/components/ui/toast-context";
import { formatCurrency, formatDate } from "@/lib/utils";

import { DelegationsSection } from "./DelegationsSection";

const PAGE_SIZE = 20;

interface Decision {
  item: QueueItem;
  mode: "approve" | "reject";
}

export function ApprovalsPage() {
  const { showToast } = useToast();
  const [page, setPage] = useState(1);
  const [decision, setDecision] = useState<Decision | null>(null);
  const { data, isLoading, isError } = useApprovalQueue(page, PAGE_SIZE);
  const decide = useDecide();

  const submit = async (comment: string) => {
    if (!decision) return;
    try {
      await decide.mutateAsync({
        documentType: decision.item.document_type,
        documentId: decision.item.document_id,
        approve: decision.mode === "approve",
        comment: comment || undefined,
      });
      showToast(decision.mode === "approve" ? "Approved" : "Rejected");
      setDecision(null);
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  const columns: Column<QueueItem>[] = [
    { header: "Type", accessor: (row) => DOCUMENT_TYPE_LABELS[row.document_type] },
    {
      header: "Number",
      accessor: (row) => {
        const link = documentLink(row.document_type, row.document_id, row.po_id);
        return link ? (
          <Link to={link} className="font-medium text-brand hover:underline">
            {row.label}
          </Link>
        ) : (
          row.label
        );
      },
    },
    { header: "Title", accessor: (row) => row.title },
    { header: "Requester", accessor: (row) => row.requester.full_name },
    { header: "Amount", accessor: (row) => formatCurrency(row.amount_base), isAmount: true },
    {
      header: "Step",
      accessor: (row) => (
        <div>
          <span>
            {row.step_order} of {row.steps_total}
          </span>
          {row.on_behalf_of && <p className="text-xs text-text-secondary">on behalf of {row.on_behalf_of.full_name}</p>}
        </div>
      ),
    },
    { header: "Submitted", accessor: (row) => formatDate(row.submitted_at) },
    {
      header: "Decision",
      accessor: (row) => (
        <div className="flex gap-2">
          <Button
            size="sm"
            aria-label={`Approve ${row.label}`}
            onClick={() => setDecision({ item: row, mode: "approve" })}
          >
            Approve
          </Button>
          <Button
            size="sm"
            variant="danger"
            aria-label={`Reject ${row.label}`}
            onClick={() => setDecision({ item: row, mode: "reject" })}
          >
            Reject
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="My approvals" description="Requests, orders and order changes waiting for your decision." />

      <Card>
        {isError ? (
          <ErrorState message="Your approvals could not be loaded." />
        ) : (
          <DataTable
            columns={columns}
            rows={data?.items ?? []}
            keyExtractor={(row) => `${row.document_type}-${row.document_id}`}
            isLoading={isLoading}
            emptyTitle="Nothing is waiting for you"
            emptyDescription="When someone submits something you can approve, it appears here."
          />
        )}
        {data && (
          <Pagination
            page={page}
            totalPages={Math.max(1, Math.ceil(data.total / PAGE_SIZE))}
            total={data.total}
            pageSize={PAGE_SIZE}
            onPageChange={setPage}
          />
        )}
      </Card>

      <DelegationsSection />

      <DecisionDialog
        isOpen={decision !== null}
        mode={decision?.mode ?? "approve"}
        subject={decision ? `${decision.item.label} · ${decision.item.title}` : ""}
        isSubmitting={decide.isPending}
        onClose={() => setDecision(null)}
        onSubmit={(comment) => void submit(comment)}
      />
    </div>
  );
}
