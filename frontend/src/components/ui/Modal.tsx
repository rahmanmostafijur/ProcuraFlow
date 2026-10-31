import { X } from "lucide-react";
import { type ReactNode, useId, useRef } from "react";

import { cn } from "@/lib/utils";

import { FOCUS_RING } from "./focus";
import { useOverlay } from "./use-overlay";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  size?: "sm" | "md" | "lg";
  description?: string;
  footer?: ReactNode;
  /** Pointer users can click outside to close. Turn off for forms with unsaved input. */
  closeOnBackdrop?: boolean;
}

const SIZES = { sm: "max-w-md", md: "max-w-xl", lg: "max-w-3xl" } as const;

export function Modal({
  isOpen,
  onClose,
  title,
  children,
  size = "md",
  description,
  footer,
  closeOnBackdrop = true,
}: ModalProps) {
  const titleId = useId();
  const descriptionId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  useOverlay({ active: isOpen, onClose, containerRef: panelRef });

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Keyboard users have Escape and the close button, so the backdrop click is a pointer convenience only. */}
      <div
        className="scrim absolute inset-0 animate-fade-in"
        aria-hidden="true"
        onClick={closeOnBackdrop ? onClose : undefined}
      />
      <div
        ref={panelRef}
        tabIndex={-1}
        className={cn(
          "relative w-full animate-pop-in rounded-overlay border border-border bg-surface-raised text-text-primary shadow-elev-3",
          "focus:outline-none",
          SIZES[size],
        )}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
      >
        <div className="flex items-start justify-between gap-4 border-b border-border px-6 py-4">
          <div>
            <h2 id={titleId} className="text-title text-text-primary">
              {title}
            </h2>
            {description && (
              <p id={descriptionId} className="mt-1 text-sm text-text-secondary">
                {description}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className={cn("rounded-control p-1 text-text-secondary hover:bg-bg hover:text-text-primary", FOCUS_RING)}
            aria-label="Close"
          >
            <X aria-hidden="true" className="h-5 w-5" />
          </button>
        </div>
        <div data-overlay-body className="max-h-[75vh] overflow-y-auto px-6 py-4">
          {children}
        </div>
        {footer && <div className="flex justify-end gap-3 border-t border-border px-6 py-4">{footer}</div>}
      </div>
    </div>
  );
}
