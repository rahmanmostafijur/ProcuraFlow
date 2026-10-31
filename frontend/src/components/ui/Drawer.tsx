import { X } from "lucide-react";
import { type ReactNode, useId, useRef } from "react";

import { cn } from "@/lib/utils";

import { FOCUS_RING } from "./focus";
import { useOverlay } from "./use-overlay";

interface DrawerProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  side?: "right" | "left";
  footer?: ReactNode;
}

/** A side sheet. It is only mounted while open, so closed drawers cost nothing and cannot hold focus. */
export function Drawer({ isOpen, onClose, title, children, side = "right", footer }: DrawerProps) {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  useOverlay({ active: isOpen, onClose, containerRef: panelRef });

  if (!isOpen) return null;
  const isRight = side === "right";

  return (
    <div className="fixed inset-0 z-50">
      {/* Pointer users can click outside to close; keyboard users have Escape and the close button. */}
      <div className="scrim absolute inset-0 animate-fade-in" aria-hidden="true" onClick={onClose} />
      <div
        ref={panelRef}
        tabIndex={-1}
        className={cn(
          "absolute top-0 flex h-full w-full max-w-md flex-col border-border bg-surface-raised text-text-primary shadow-elev-3 focus:outline-none",
          isRight ? "right-0 animate-slide-in-right border-l" : "left-0 animate-slide-in-left border-r",
        )}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <h2 id={titleId} className="text-title text-text-primary">
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className={cn("rounded-control p-1 text-text-secondary hover:bg-bg hover:text-text-primary", FOCUS_RING)}
            aria-label="Close"
          >
            <X aria-hidden="true" className="h-5 w-5" />
          </button>
        </div>
        <div data-overlay-body className="flex-1 overflow-y-auto px-6 py-4">
          {children}
        </div>
        {footer && <div className="flex justify-end gap-3 border-t border-border px-6 py-4">{footer}</div>}
      </div>
    </div>
  );
}
