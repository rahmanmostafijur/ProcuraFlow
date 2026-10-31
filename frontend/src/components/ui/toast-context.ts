import { createContext, useContext } from "react";

export type ToastType = "success" | "error" | "info" | "warning";

export interface ToastOptions {
  message: string;
  title?: string;
  type?: ToastType;
  /** Milliseconds before it dismisses itself; 0 keeps it until dismissed. Defaults by type. */
  durationMs?: number;
  action?: { label: string; onClick: () => void };
}

export const DEFAULT_DURATION: Record<ToastType, number> = { success: 5000, info: 5000, warning: 8000, error: 8000 };

export interface ToastContextValue {
  /** Original signature, kept so existing screens do not change. */
  showToast: (message: string, type?: ToastType) => number;
  toast: (options: ToastOptions) => number;
  dismiss: (id: number) => void;
}

// The provider lives in ToastProvider.tsx: a module that exports a component and anything else
// cannot be hot-reloaded by React Fast Refresh.
export const ToastContext = createContext<ToastContextValue | undefined>(undefined);

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return ctx;
}
