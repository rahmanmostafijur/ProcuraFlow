import { type ReactNode, useCallback, useMemo, useRef, useState } from "react";

import { type ToastData, ToastView } from "./Toast";
import { ToastContext, type ToastContextValue, type ToastOptions, type ToastType } from "./toast-context";

const MAX_VISIBLE = 5;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastData[]>([]);
  const [paused, setPaused] = useState(false);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => setToasts((prev) => prev.filter((item) => item.id !== id)), []);

  const toast = useCallback((options: ToastOptions) => {
    const id = nextId.current++;
    const item: ToastData = { ...options, id, type: options.type ?? "success" };
    // Newest last; the oldest drops off when the stack is full so it never covers the screen.
    setToasts((prev) => [...prev, item].slice(-MAX_VISIBLE));
    return id;
  }, []);

  const showToast = useCallback((message: string, type: ToastType = "success") => toast({ message, type }), [toast]);
  const value = useMemo<ToastContextValue>(() => ({ showToast, toast, dismiss }), [showToast, toast, dismiss]);

  const polite = toasts.filter((item) => item.type !== "error");
  const assertive = toasts.filter((item) => item.type === "error");

  // Plain aria-live regions (no status/alert role, which screens and their tests use for inline messages).
  // Both live regions stay mounted so a screen reader hears the first toast too. Errors interrupt (assertive).
  const renderList = (items: ToastData[]) =>
    items.map((item) => <ToastView key={item.id} toast={item} onDismiss={dismiss} paused={paused} />);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        className="pointer-events-none fixed bottom-4 right-4 z-[100] flex flex-col items-end gap-2"
        onFocus={() => setPaused(true)}
        onBlur={() => setPaused(false)}
      >
        <div aria-live="polite" aria-relevant="additions" className="flex flex-col items-end gap-2">
          {renderList(polite)}
        </div>
        <div aria-live="assertive" className="flex flex-col items-end gap-2">
          {renderList(assertive)}
        </div>
      </div>
    </ToastContext.Provider>
  );
}
