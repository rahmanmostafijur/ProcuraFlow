import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface CardProps {
  className?: string;
  children: ReactNode;
  /** Legacy callers pad their own content, so the default stays none. */
  padding?: "none" | "md" | "lg";
}

const PADDING = { none: "", md: "p-4", lg: "p-6" } as const;

export function Card({ className, children, padding = "none" }: CardProps) {
  return (
    <div
      className={cn(
        "rounded-card border border-border bg-surface text-text-primary shadow-elev-1",
        PADDING[padding],
        className,
      )}
    >
      {children}
    </div>
  );
}
