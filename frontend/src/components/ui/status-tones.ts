export type StatusTone = "neutral" | "success" | "warning" | "danger" | "info" | "attention";

/**
 * Document and record statuses (the same keys the legacy Badge colours) mapped to a meaning, not a colour:
 * neutral = no decision yet, warning = waiting on someone, info = in progress, attention = needs a look,
 * success = done, danger = refused or over limit.
 */
export const STATUS_TONES: Record<string, StatusTone> = {
  draft: "neutral",
  submitted: "warning",
  approved: "info",
  ordered: "info",
  partially_received: "attention",
  received: "success",
  cancelled: "danger",
  active: "success",
  inactive: "neutral",
  pending: "neutral",
  on_time: "success",
  delayed: "danger",
  partial: "attention",
  rejected: "danger",
  converted: "info",
  skipped: "neutral",
  ok: "success",
  warning: "warning",
  over: "danger",
  applied: "success",
  pending_approval: "warning",
  valid: "success",
  expiring_soon: "warning",
  expired: "danger",
  released: "success",
  paid: "success",
  unpaid: "warning",
  overdue: "danger",
  matched: "info",
  exception: "attention",
  on_hold: "warning",
  void: "neutral",
};

/** "partially_received" becomes "Partially received". */
export function statusLabel(status: string): string {
  const spaced = status.replace(/_/g, " ").trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}
