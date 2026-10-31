import { cn } from "@/lib/utils";

import { VisuallyHidden } from "./VisuallyHidden";

interface SpinnerProps {
  className?: string;
  /** When given, the spinner is announced as a status; otherwise it is decoration next to visible text. */
  label?: string;
}

export function Spinner({ className, label }: SpinnerProps) {
  const ring = (
    <span
      aria-hidden="true"
      className={cn(
        "inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent",
        className,
      )}
    />
  );
  if (!label) return ring;
  return (
    <span role="status" className="inline-flex items-center">
      {ring}
      <VisuallyHidden>{label}</VisuallyHidden>
    </span>
  );
}
