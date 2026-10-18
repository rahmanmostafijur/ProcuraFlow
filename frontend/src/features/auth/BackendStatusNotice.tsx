import { READINESS_BUDGET_MS } from "@/api/readiness";
import { Button } from "@/components/ui/Button";
import type { BackendStatus } from "@/lib/use-backend-readiness";

interface BackendStatusNoticeProps {
  status: BackendStatus;
  elapsedMs: number;
  onRetry: () => void;
}

export function BackendStatusNotice({ status, elapsedMs, onRetry }: BackendStatusNoticeProps) {
  if (status === "waking") {
    const percent = Math.min(100, Math.round((elapsedMs / READINESS_BUDGET_MS) * 100));
    const seconds = Math.floor(elapsedMs / 1000);
    return (
      <div role="status" className="mb-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
        <p className="font-medium">Waking the demo server…</p>
        <p className="mt-1 text-amber-800">
          The free hosting tier sleeps when idle and takes up to a minute to start. {seconds}s of up to{" "}
          {READINESS_BUDGET_MS / 1000}s.
        </p>
        <div
          role="progressbar"
          aria-label="Waking the demo server"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent}
          className="mt-2 h-1.5 overflow-hidden rounded-full bg-amber-200"
        >
          <div className="h-full bg-amber-500 transition-[width] duration-500" style={{ width: `${percent}%` }} />
        </div>
      </div>
    );
  }

  if (status === "unavailable") {
    return (
      <div role="alert" className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
        <p className="font-medium">We couldn&apos;t reach the server.</p>
        <p className="mt-1">It didn&apos;t respond in time. Check your connection, then try again.</p>
        <Button type="button" variant="secondary" size="sm" className="mt-3" onClick={onRetry}>
          Try again
        </Button>
      </div>
    );
  }

  return null;
}
