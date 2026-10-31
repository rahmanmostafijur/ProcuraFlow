import { useState, type ReactNode } from "react";

import { extractErrorMessage } from "@/api/client";
import { exportSubjectData, useAnonymise, type GdprSubject } from "@/api/gdpr";
import { useSuppliers } from "@/api/suppliers";
import { useUsers } from "@/api/users";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { useToast } from "@/components/ui/toast-context";
import { cn } from "@/lib/utils";

import { AnonymiseDialog } from "./AnonymiseDialog";

const LIST_SIZE = 20;

interface Subject {
  id: number;
  name: string;
  detail: string;
}

interface Target {
  subject: GdprSubject;
  id: number;
  name: string;
}

interface SourceProps {
  search: string;
  children: (rows: Subject[], isLoading: boolean) => ReactNode;
}

// One component per list, so only the visible kind is fetched.
function UserSource({ search, children }: SourceProps) {
  const { data, isLoading } = useUsers(1, LIST_SIZE, search.trim() || undefined);
  const rows = (data?.items ?? []).map((user) => ({ id: user.id, name: user.full_name, detail: user.email }));
  return <>{children(rows, isLoading)}</>;
}

function SupplierSource({ search, children }: SourceProps) {
  const { data, isLoading } = useSuppliers({ page: 1, page_size: LIST_SIZE, search: search.trim() || undefined });
  const rows = (data?.items ?? []).map((supplier) => ({
    id: supplier.id,
    name: supplier.contact_name ?? "No contact person",
    detail: `${supplier.name}${supplier.email ? ` · ${supplier.email}` : ""}`,
  }));
  return <>{children(rows, isLoading)}</>;
}

const TABS: { kind: GdprSubject; label: string }[] = [
  { kind: "users", label: "User accounts" },
  { kind: "suppliers", label: "Supplier contacts" },
];

export function GdprPage() {
  const { showToast } = useToast();
  const [kind, setKind] = useState<GdprSubject>("users");
  const [search, setSearch] = useState("");
  const [target, setTarget] = useState<Target | null>(null);
  const [refusal, setRefusal] = useState<string | null>(null);
  const Source = kind === "users" ? UserSource : SupplierSource;
  const anonymise = useAnonymise(target?.subject ?? kind);

  const exportData = async (row: Subject) => {
    try {
      await exportSubjectData(kind, row.id);
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  const confirm = async () => {
    if (!target) return;
    try {
      await anonymise.mutateAsync(target.id);
      showToast(`${target.name} was anonymised`);
      setTarget(null);
      setRefusal(null);
    } catch (error) {
      setRefusal(extractErrorMessage(error));
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Personal data (GDPR)</h1>
        <p className="text-sm text-slate-500">
          Export what is stored about a person, or anonymise them. Both are recorded in the audit log.
        </p>
      </div>
      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 p-4">
          <div role="tablist" className="flex gap-1">
            {TABS.map((tab) => (
              <button
                key={tab.kind}
                role="tab"
                aria-selected={kind === tab.kind}
                onClick={() => setKind(tab.kind)}
                className={cn(
                  "rounded-md px-3 py-1.5 text-sm font-medium",
                  kind === tab.kind ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-50",
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <Input
            aria-label="Search people"
            placeholder="Search…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="max-w-xs"
          />
        </div>
        <Source search={search}>
          {(rows, isLoading) => (
            <>
              {isLoading && <p className="p-4 text-sm text-slate-500">Loading…</p>}
              {!isLoading && rows.length === 0 && (
                <p className="p-4 text-sm text-slate-500">Nobody matches your search.</p>
              )}
              <ul className="divide-y divide-slate-100">
                {rows.map((row) => (
                  <li key={row.id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
                    <div className="min-w-0">
                      <p className="truncate font-medium text-slate-900">{row.name}</p>
                      <p className="truncate text-xs text-slate-500">{row.detail}</p>
                    </div>
                    <div className="flex shrink-0 gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        aria-label={`Export data of ${row.name}`}
                        onClick={() => void exportData(row)}
                      >
                        Export JSON
                      </Button>
                      <Button
                        variant="danger"
                        size="sm"
                        aria-label={`Anonymise ${row.name}`}
                        onClick={() => {
                          setRefusal(null);
                          setTarget({ subject: kind, id: row.id, name: row.name });
                        }}
                      >
                        Anonymise
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}
        </Source>
      </Card>
      <AnonymiseDialog
        subjectName={target?.name ?? null}
        isLoading={anonymise.isPending}
        error={refusal}
        onConfirm={() => void confirm()}
        onCancel={() => setTarget(null)}
      />
    </div>
  );
}
