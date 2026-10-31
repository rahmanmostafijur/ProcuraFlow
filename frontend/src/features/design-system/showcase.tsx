import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** One anchored block of the design-system page. */
export function Section({
  id,
  title,
  intro,
  children,
}: {
  id: string;
  title: string;
  intro?: string;
  children: ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="scroll-mt-6 space-y-5">
      <div>
        <h2 id={`${id}-title`} className="text-display-sm text-text-primary">
          {title}
        </h2>
        {intro && <p className="mt-1 max-w-3xl text-body text-text-secondary">{intro}</p>}
      </div>
      {children}
    </section>
  );
}

export function SubHeading({ children }: { children: ReactNode }) {
  return <h3 className="mb-2 text-caption uppercase text-text-secondary">{children}</h3>;
}

/** A labelled cell in a state matrix (Default, Hover, Focus, Disabled...). */
export function StateCell({ label, children, className }: { label: string; children: ReactNode; className?: string }) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <p className="text-xs font-medium text-text-secondary">{label}</p>
      <div>{children}</div>
    </div>
  );
}

export function StateRow({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap items-start gap-x-6 gap-y-4">{children}</div>;
}

/**
 * Shows the same content in the current theme and again inside a container forced to dark (the `dark` class for
 * Tailwind's variants and `theme-dark` for the token variables), so both themes are visible at once.
 */
export function ThemePair({ children }: { children: ReactNode }) {
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <div className="min-w-0 rounded-card border border-border bg-bg p-4 text-text-primary">
        <p className="mb-3 text-xs font-semibold uppercase text-text-secondary">Current theme</p>
        {children}
      </div>
      <div className="dark theme-dark min-w-0 rounded-card border border-border bg-bg p-4 text-text-primary">
        <p className="mb-3 text-xs font-semibold uppercase text-text-secondary">Dark (forced)</p>
        {children}
      </div>
    </div>
  );
}

export interface TocEntry {
  id: string;
  label: string;
}

export function TableOfContents({ entries }: { entries: TocEntry[] }) {
  return (
    <nav aria-label="Components" className="text-sm">
      <p className="mb-2 text-caption uppercase text-text-secondary">On this page</p>
      <ul className="space-y-1">
        {entries.map((entry) => (
          <li key={entry.id}>
            <a
              href={`#${entry.id}`}
              className="block rounded-control px-2 py-1 text-text-secondary hover:bg-surface hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              {entry.label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
