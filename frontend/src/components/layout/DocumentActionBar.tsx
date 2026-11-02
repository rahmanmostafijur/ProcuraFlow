import { Children, type ReactNode } from "react";

interface DocumentActionBarProps {
  /** Only the actions the signed-in user may take right now; the bar renders nothing when there are none. */
  children: ReactNode;
  label?: string;
}

/** Sticks to the bottom of the scrolling page so the document's actions stay reachable on long documents. */
export function DocumentActionBar({ children, label = "Document actions" }: DocumentActionBarProps) {
  if (Children.toArray(children).length === 0) return null;
  return (
    <div
      role="toolbar"
      aria-label={label}
      className="sticky bottom-0 z-10 -mx-4 mt-6 flex flex-wrap items-center justify-end gap-2 border-t border-border bg-surface px-4 py-3 shadow-elev-2 md:-mx-6 md:px-6"
    >
      {children}
    </div>
  );
}
