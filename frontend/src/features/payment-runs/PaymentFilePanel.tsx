import { Download, FileText } from "lucide-react";
import axios from "axios";
import { useState } from "react";

import { extractErrorMessage } from "@/api/client";
import {
  downloadPaymentFile,
  FILE_FORMAT_LABELS,
  parseExportProblems,
  useGeneratePaymentFile,
  usePaymentFile,
} from "@/api/paymentRuns";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/toast-context";
import { formatCurrency, formatDateTime } from "@/lib/utils";

/** Generates the bank file of a released run once; afterwards the same stored file is downloaded. */
export function PaymentFilePanel({ runId }: { runId: number }) {
  const { showToast } = useToast();
  const { data: file, isLoading } = usePaymentFile(runId, true);
  const generate = useGeneratePaymentFile(runId);
  const [problems, setProblems] = useState<string[]>([]);

  const handleGenerate = async () => {
    setProblems([]);
    try {
      await generate.mutateAsync();
      showToast("Payment file generated");
    } catch (error) {
      const detail = extractErrorMessage(error);
      // 422 lists what is missing per supplier; other refusals are a single sentence.
      if (axios.isAxiosError(error) && error.response?.status === 422) setProblems(parseExportProblems(detail));
      else showToast(detail, "error");
    }
  };

  const handleDownload = async () => {
    if (!file) return;
    try {
      await downloadPaymentFile(file);
    } catch {
      showToast("The file could not be downloaded. Please try again.", "error");
    }
  };

  return (
    <section aria-label="Payment file" className="space-y-3 rounded-control border border-border p-4">
      <h3 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
        <FileText className="h-4 w-4" /> Payment file
      </h3>
      {isLoading && <p className="text-sm text-text-secondary">Checking for a file…</p>}
      {file && (
        <>
          <dl className="grid gap-1 text-sm sm:grid-cols-2">
            <dt className="text-text-secondary">Format</dt>
            <dd>{FILE_FORMAT_LABELS[file.file_format]}</dd>
            <dt className="text-text-secondary">File</dt>
            <dd>{file.filename}</dd>
            <dt className="text-text-secondary">Payments</dt>
            <dd>
              {file.transaction_count} · {formatCurrency(file.total, file.currency_code)}
            </dd>
            <dt className="text-text-secondary">Generated</dt>
            <dd>
              {formatDateTime(file.created_at)} by {file.created_by.full_name}
            </dd>
            <dt className="text-text-secondary">SHA-256</dt>
            <dd className="break-all font-mono text-xs">{file.sha256}</dd>
          </dl>
          <Button variant="secondary" onClick={() => void handleDownload()}>
            <Download className="h-4 w-4" /> Download file
          </Button>
        </>
      )}
      {file === null && (
        <Button disabled={generate.isPending} onClick={() => void handleGenerate()}>
          {generate.isPending ? "Generating…" : "Generate payment file"}
        </Button>
      )}
      {problems.length > 0 && (
        <div role="alert" className="rounded-control bg-danger-bg px-3 py-2 text-sm text-danger-fg">
          <p className="font-medium">The file cannot be generated until these are fixed:</p>
          <ul className="mt-1 list-disc pl-5">
            {problems.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
