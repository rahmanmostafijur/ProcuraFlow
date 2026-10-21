import { createContext, useContext } from "react";

export type ToastType = "success" | "error";

export interface ToastContextValue {
  showToast: (message: string, type?: ToastType) => void;
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
