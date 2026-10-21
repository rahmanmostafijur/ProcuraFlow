import { type ReactNode, useEffect, useId } from "react";
import { X } from "lucide-react";

interface DrawerProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}

export function Drawer({ isOpen, onClose, title, children }: DrawerProps) {
  const titleId = useId();

  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [isOpen, onClose]);

  return (
    <div
      className={isOpen ? "pointer-events-auto fixed inset-0 z-50" : "pointer-events-none fixed inset-0 z-50"}
      aria-hidden={!isOpen}
    >
      <div
        className={`absolute inset-0 bg-slate-900/40 transition-opacity ${isOpen ? "opacity-100" : "opacity-0"}`}
        // Pointer users can click outside to close; keyboard users have Escape and the close button.
        aria-hidden="true"
        onClick={onClose}
      />
      <div
        className={`absolute right-0 top-0 h-full w-full max-w-md transform bg-white shadow-xl transition-transform ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <h2 id={titleId} className="text-lg font-semibold text-slate-900">
            {title}
          </h2>
          <button type="button" onClick={onClose} className="text-slate-400 hover:text-slate-600" aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="h-[calc(100%-65px)] overflow-y-auto px-6 py-4">{children}</div>
      </div>
    </div>
  );
}
