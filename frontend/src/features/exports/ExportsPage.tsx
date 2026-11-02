import { Download } from "lucide-react";
import { useState } from "react";

import { downloadExport, EXPORT_KINDS, type ExportFilters, type ExportKind } from "@/api/exports";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Select } from "@/components/ui/Select";
import { PageHeader } from "@/components/ui/PageHeader";
import { useToast } from "@/components/ui/toast-context";

const NO_FILTERS: ExportFilters = { date_from: "", date_to: "", status: "" };

function ExportCard({ kind }: { kind: ExportKind }) {
  const { showToast } = useToast();
  const [filters, setFilters] = useState<ExportFilters>(NO_FILTERS);
  const [isBusy, setBusy] = useState(false);
  const hasStatuses = kind.statuses.length > 0;
  const idPrefix = `export-${kind.key}`;

  const download = async () => {
    setBusy(true);
    try {
      await downloadExport(kind, filters);
    } catch {
      // The error body of a blob request is a Blob, so the API's detail is not readable here.
      showToast("The export could not be downloaded. Please try again.", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="p-5">
      <h2 className="text-base font-semibold text-text-primary">{kind.label}</h2>
      <p className="mb-4 text-sm text-text-secondary">{kind.description}</p>
      <div className="grid gap-3 sm:grid-cols-3">
        <div>
          <Label htmlFor={`${idPrefix}-from`}>From</Label>
          <Input
            id={`${idPrefix}-from`}
            type="date"
            aria-label={`${kind.label} from date`}
            value={filters.date_from}
            onChange={(event) => setFilters({ ...filters, date_from: event.target.value })}
          />
        </div>
        <div>
          <Label htmlFor={`${idPrefix}-to`}>To</Label>
          <Input
            id={`${idPrefix}-to`}
            type="date"
            aria-label={`${kind.label} to date`}
            value={filters.date_to}
            onChange={(event) => setFilters({ ...filters, date_to: event.target.value })}
          />
        </div>
        {hasStatuses && (
          <div>
            <Label htmlFor={`${idPrefix}-status`}>Status</Label>
            <Select
              id={`${idPrefix}-status`}
              aria-label={`${kind.label} status`}
              value={filters.status}
              onChange={(event) => setFilters({ ...filters, status: event.target.value })}
            >
              <option value="">Any status</option>
              {kind.statuses.map((status) => (
                <option key={status} value={status}>
                  {status.replace(/_/g, " ")}
                </option>
              ))}
            </Select>
          </div>
        )}
      </div>
      <div className="mt-4 flex justify-end">
        <Button disabled={isBusy} onClick={() => void download()} aria-label={`Download ${kind.label}`}>
          <Download className="h-4 w-4" /> {isBusy ? "Preparing…" : "Download CSV"}
        </Button>
      </div>
    </Card>
  );
}

export function ExportsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Accounting exports"
        description="CSV files for your accounting system. Leave a filter empty to include everything."
      />
      <div className="grid gap-4 lg:grid-cols-2">
        {EXPORT_KINDS.map((kind) => (
          <ExportCard key={kind.key} kind={kind} />
        ))}
      </div>
    </div>
  );
}
