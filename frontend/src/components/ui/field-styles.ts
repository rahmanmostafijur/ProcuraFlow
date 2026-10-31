import { cn } from "@/lib/utils";

import { FOCUS_RING_ALWAYS } from "./focus";

/** Shared look for text input, textarea and select. An invalid field also gets a thicker border, not just a colour. */
export function controlClasses(invalid: boolean, extra?: string): string {
  return cn(
    "w-full rounded-control border bg-surface px-3 py-2 text-sm text-text-primary shadow-elev-1 placeholder:text-text-muted",
    "disabled:cursor-not-allowed disabled:bg-bg disabled:opacity-60",
    FOCUS_RING_ALWAYS,
    invalid ? "border-2 border-danger-solid" : "border-border-strong",
    extra,
  );
}
