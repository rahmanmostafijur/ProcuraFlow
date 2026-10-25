import { useApprovalHistory } from "@/api/approvals";
import type { ApprovalDocumentType, ApprovalStep } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { formatDateTime } from "@/lib/utils";

interface ApprovalTimelineProps {
  documentType: ApprovalDocumentType;
  documentId: number;
}

function groupByRound(steps: ApprovalStep[]): [number, ApprovalStep[]][] {
  const rounds = new Map<number, ApprovalStep[]>();
  for (const step of steps) rounds.set(step.round, [...(rounds.get(step.round) ?? []), step]);
  return [...rounds.entries()].sort(([a], [b]) => a - b);
}

function StepRow({ step }: { step: ApprovalStep }) {
  return (
    <li className="space-y-1 py-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium text-slate-900">
          Step {step.step_order}: {step.approver_label}
        </span>
        <Badge status={step.status}>{step.status}</Badge>
      </div>
      {step.decided_by_person && (
        <p className="text-slate-600">
          {step.status === "rejected" ? "Rejected" : "Decided"} by {step.decided_by_person.full_name}
          {step.on_behalf_of_person && ` on behalf of ${step.on_behalf_of_person.full_name}`}
          {step.decided_at && ` · ${formatDateTime(step.decided_at)}`}
        </p>
      )}
      {step.comment && <p className="text-slate-600">“{step.comment}”</p>}
    </li>
  );
}

export function ApprovalTimeline({ documentType, documentId }: ApprovalTimelineProps) {
  const { data: steps, isLoading, isError } = useApprovalHistory(documentType, documentId);
  const rounds = groupByRound(steps ?? []);

  return (
    <Card className="p-5">
      <h2 className="mb-2 text-sm font-semibold text-slate-900">Approval history</h2>
      {isLoading && <p className="text-sm text-slate-500">Loading approval history…</p>}
      {isError && <p className="text-sm text-red-600">The approval history could not be loaded.</p>}
      {steps && steps.length === 0 && <p className="text-sm text-slate-500">No approval has been needed yet.</p>}
      {rounds.map(([round, roundSteps]) => (
        <section key={round} aria-label={`Approval round ${round}`}>
          {rounds.length > 1 && <h3 className="mt-2 text-xs font-semibold uppercase text-slate-500">Round {round}</h3>}
          <ul className="divide-y divide-slate-100">
            {roundSteps.map((step) => (
              <StepRow key={step.id} step={step} />
            ))}
          </ul>
        </section>
      ))}
    </Card>
  );
}
