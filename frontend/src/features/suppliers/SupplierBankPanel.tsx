import { useState } from "react";

import { extractErrorMessage } from "@/api/client";
import { maskIdentifier, useBankDetails, useDecideBankChange, type BankDetails } from "@/api/supplierBank";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useAuth } from "@/lib/auth-context";
import { formatDateTime } from "@/lib/utils";

import { BankChangeForm } from "./BankChangeForm";

function DetailsList({ details }: { details: BankDetails }) {
  const rows: [string, string][] = [
    ["Account holder", details.bank_account_name ?? "—"],
    ["Country", details.bank_country ?? "—"],
    ["IBAN", maskIdentifier(details.iban)],
    ["BIC", details.bic ?? "—"],
    ["Account number", maskIdentifier(details.bank_account_number)],
    ["Routing number", details.routing_number ?? "—"],
  ];
  return (
    <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
      {rows.map(([label, value]) => (
        <div key={label} className="flex justify-between gap-3">
          <dt className="text-text-secondary">{label}</dt>
          <dd className="font-mono text-text-primary">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Changing bank details needs a second person: the requester sees their change wait, never approve. */
export function SupplierBankPanel({ supplierId }: { supplierId: number }) {
  const { user } = useAuth();
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const { data, isLoading, isError } = useBankDetails(supplierId);
  const decide = useDecideBankChange(supplierId);

  const run = async (changeId: number, decision: "approve" | "reject") => {
    setDecisionError(null);
    try {
      await decide.mutateAsync({ changeId, decision });
    } catch (error) {
      setDecisionError(extractErrorMessage(error));
    }
  };

  const pending = data?.pending;
  const isOwnChange = pending !== null && pending !== undefined && pending.requested_by.id === user?.id;

  return (
    <Card className="space-y-4 p-6">
      <div>
        <h2 className="text-base font-semibold text-text-primary">Bank details</h2>
        <p className="text-sm text-text-secondary">
          Account numbers are masked. A change needs approval by a second person.
        </p>
      </div>
      {isLoading && <p className="text-sm text-text-secondary">Loading bank details…</p>}
      {isError && <p className="text-sm text-danger-fg">The bank details could not be loaded.</p>}
      {data && (
        <>
          <section aria-label="Current bank details">
            <h3 className="mb-2 text-sm font-semibold text-text-primary">Current</h3>
            {data.current ? (
              <DetailsList details={data.current} />
            ) : (
              <p className="text-sm text-text-secondary">No approved bank details yet.</p>
            )}
          </section>
          {pending && (
            <section
              aria-label="Pending change"
              className="rounded-control border border-warning-fg/30 bg-warning-bg p-4"
            >
              <div className="mb-2 flex items-center gap-2">
                <h3 className="text-sm font-semibold text-text-primary">Pending change</h3>
                <StatusBadge status="pending_approval" label="Waiting for approval" />
              </div>
              <p className="mb-2 text-xs text-text-secondary">
                Requested by {pending.requested_by.full_name} on {formatDateTime(pending.requested_at)}
              </p>
              <DetailsList details={pending} />
              {isOwnChange ? (
                <p className="mt-3 text-sm text-text-secondary">
                  You requested this change, so someone else has to approve it.
                </p>
              ) : (
                <div className="mt-3 flex gap-2">
                  <Button size="sm" disabled={decide.isPending} onClick={() => void run(pending.id, "approve")}>
                    Approve change
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={decide.isPending}
                    onClick={() => void run(pending.id, "reject")}
                  >
                    Reject change
                  </Button>
                </div>
              )}
              {decisionError && (
                <p role="alert" className="mt-3 text-sm text-danger-fg">
                  {decisionError}
                </p>
              )}
            </section>
          )}
          {!pending && <BankChangeForm supplierId={supplierId} />}
          {data.history.length > 0 && (
            <section aria-label="Bank details history">
              <h3 className="mb-2 text-sm font-semibold text-text-primary">History</h3>
              <ul className="divide-y divide-border text-sm">
                {data.history.map((entry) => (
                  <li key={entry.id} className="flex justify-between gap-3 py-2">
                    <span className="font-mono">{maskIdentifier(entry.iban ?? entry.bank_account_number)}</span>
                    <span className="text-text-secondary">
                      {entry.status} · {formatDateTime(entry.decided_at ?? entry.requested_at)}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </Card>
  );
}
