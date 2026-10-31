import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

import { FOCUS_RING } from "./focus";
import { DEFAULT_DURATION, type ToastOptions, type ToastType } from "./toast-context";

export interface ToastData extends ToastOptions {
  id: number;
  type: ToastType;
}

const STYLES: Record<ToastType, { box: string; Icon: typeof Info; word: string }> = {
  success: { box: "border-brand bg-success-bg text-success-fg", Icon: CheckCircle2, word: "Success" },
  info: { box: "border-border-strong bg-info-bg text-info-fg", Icon: Info, word: "Information" },
  warning: { box: "border-border-strong bg-warning-bg text-warning-fg", Icon: AlertTriangle, word: "Warning" },
  error: { box: "border-danger-solid bg-danger-bg text-danger-fg", Icon: XCircle, word: "Error" },
};

interface ToastViewProps {
  toast: ToastData;
  onDismiss: (id: number) => void;
  /** True while the pointer or focus is inside the stack: every timer waits. */
  paused: boolean;
}

/** One toast. Its timer keeps the remaining time, so pausing and resuming does not restart the countdown. */
export function ToastView({ toast, onDismiss, paused }: ToastViewProps) {
  const { id, type, title, message, action } = toast;
  const duration = toast.durationMs ?? DEFAULT_DURATION[type];
  const remaining = useRef(duration);
  const [hovered, setHovered] = useState(false);
  const isPaused = paused || hovered;
  const { box, Icon, word } = STYLES[type];

  useEffect(() => {
    if (duration === 0 || isPaused) return;
    const startedAt = Date.now();
    const timer = setTimeout(() => onDismiss(id), remaining.current);
    return () => {
      clearTimeout(timer);
      remaining.current -= Date.now() - startedAt;
    };
  }, [duration, isPaused, id, onDismiss]);

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className={cn(
        "pointer-events-auto flex w-80 max-w-[calc(100vw-2rem)] animate-toast-in items-start gap-2 rounded-card border-l-4 px-4 py-3 text-sm shadow-elev-2",
        box,
      )}
    >
      <Icon aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="font-semibold">
          <span className="sr-only">{word}: </span>
          {title ?? message}
        </p>
        {title && <p>{message}</p>}
        {action && (
          <button
            type="button"
            onClick={() => {
              action.onClick();
              onDismiss(id);
            }}
            className={cn("mt-1 rounded-control font-semibold underline", FOCUS_RING)}
          >
            {action.label}
          </button>
        )}
      </div>
      <button
        type="button"
        onClick={() => onDismiss(id)}
        className={cn("rounded-control p-0.5 opacity-80 hover:opacity-100", FOCUS_RING)}
        aria-label="Dismiss notification"
      >
        <X aria-hidden="true" className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
