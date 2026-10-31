import { Spinner } from "./Spinner";

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" className="flex items-center justify-center gap-2 py-16 text-sm text-text-secondary">
      <Spinner className="text-brand" />
      {label}
    </div>
  );
}
