import { AlertTriangle, CheckCircle2, CircleDashed, Clock, Info, XCircle } from "lucide-react";

import { cn } from "@/lib/utils";

import { STATUS_TONES, type StatusTone, statusLabel } from "./status-tones";

const TONES: Record<StatusTone, { classes: string; Icon: typeof Info }> = {
  neutral: { classes: "border border-border bg-bg text-text-secondary", Icon: CircleDashed },
  success: { classes: "bg-success-bg text-success-fg", Icon: CheckCircle2 },
  warning: { classes: "bg-warning-bg text-warning-fg", Icon: Clock },
  danger: { classes: "bg-danger-bg text-danger-fg", Icon: XCircle },
  info: { classes: "bg-info-bg text-info-fg", Icon: Info },
  attention: { classes: "bg-attention-bg text-attention-fg", Icon: AlertTriangle },
};

interface StatusBadgeProps {
  /** A key of STATUS_TONES, e.g. "partially_received". Unknown statuses render as neutral with their own text. */
  status: string;
  /** Override the generated label (for translated or longer text). */
  label?: string;
  className?: string;
}

/** Always icon + word: the colour is reinforcement, never the only signal. */
export function StatusBadge({ status, label, className }: StatusBadgeProps) {
  const { classes, Icon } = TONES[STATUS_TONES[status] ?? "neutral"];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium",
        classes,
        className,
      )}
    >
      <Icon aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />
      {label ?? statusLabel(status)}
    </span>
  );
}
