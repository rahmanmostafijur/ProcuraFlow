import { Check, X } from "lucide-react";

import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

export type StepState = "done" | "current" | "upcoming" | "rejected";

export interface LifecycleStep {
  id: string;
  label: string;
  state: StepState;
  description?: string;
  /** ISO timestamp the step was reached, if it has been. */
  at?: string | null;
}

interface LifecycleStepperProps {
  steps: LifecycleStep[];
  label?: string;
  /** Horizontal collapses to vertical on narrow screens so labels never truncate. */
  orientation?: "horizontal" | "vertical";
}

const STATE_WORD: Record<StepState, string> = {
  done: "completed",
  current: "current step",
  upcoming: "not started",
  rejected: "rejected",
};

function StepMarker({ state, index }: { state: StepState; index: number }) {
  // Shape differs per state (check, number in a filled ring, number, cross), so colour is not the only cue.
  const base = "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 text-sm font-semibold";
  if (state === "done") {
    return (
      <span className={cn(base, "border-brand bg-brand text-on-brand")}>
        <Check aria-hidden="true" className="h-4 w-4" strokeWidth={3} />
      </span>
    );
  }
  if (state === "rejected") {
    return (
      <span className={cn(base, "border-danger-solid bg-danger-bg text-danger-fg")}>
        <X aria-hidden="true" className="h-4 w-4" strokeWidth={3} />
      </span>
    );
  }
  if (state === "current") {
    return (
      <span
        className={cn(
          base,
          "border-brand bg-brand-subtle text-brand-subtle-fg ring-2 ring-focus ring-offset-2 ring-offset-surface",
        )}
      >
        {index + 1}
      </span>
    );
  }
  return <span className={cn(base, "border-border-strong bg-surface text-text-secondary")}>{index + 1}</span>;
}

export function LifecycleStepper({ steps, label = "Progress", orientation = "horizontal" }: LifecycleStepperProps) {
  const horizontal = orientation === "horizontal";
  return (
    <nav aria-label={label}>
      <ol className={cn("flex flex-col gap-0", horizontal && "sm:flex-row sm:gap-2")}>
        {steps.map((step, index) => {
          const isLast = index === steps.length - 1;
          return (
            <li
              key={step.id}
              aria-current={step.state === "current" ? "step" : undefined}
              className={cn("flex", horizontal ? "sm:flex-1 sm:flex-col sm:gap-2" : "", "gap-3")}
            >
              <div className={cn("flex items-center", horizontal ? "sm:w-full" : "flex-col")}>
                <StepMarker state={step.state} index={index} />
                {!isLast && (
                  <span
                    aria-hidden="true"
                    className={cn(
                      "bg-border-strong",
                      step.state === "done" && "bg-brand",
                      horizontal ? "my-1 h-6 w-0.5 sm:mx-2 sm:my-0 sm:h-0.5 sm:flex-1" : "my-1 h-6 w-0.5",
                    )}
                  />
                )}
              </div>
              <div className={cn("pb-4", horizontal && "sm:pb-0")}>
                <p
                  className={cn(
                    "text-sm font-semibold",
                    step.state === "upcoming" ? "text-text-secondary" : "text-text-primary",
                    step.state === "rejected" && "text-danger-fg",
                  )}
                >
                  {step.label}
                  <span className="sr-only"> ({STATE_WORD[step.state]})</span>
                </p>
                {step.description && <p className="text-xs text-text-secondary">{step.description}</p>}
                {step.at && <p className="text-xs text-text-secondary">{formatDate(step.at)}</p>}
              </div>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
