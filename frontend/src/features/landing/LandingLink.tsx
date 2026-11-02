import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { sizeStyles, variantStyles } from "@/components/ui/button-styles";
import { FOCUS_RING } from "@/components/ui/focus";
import { cn } from "@/lib/utils";

interface LandingLinkProps {
  to: string;
  children: ReactNode;
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md" | "lg";
  className?: string;
}

/** A router link that looks like the app's Button; navigation is a link, never a button. */
export function LandingLink({ to, children, variant = "primary", size = "md", className }: LandingLinkProps) {
  return (
    <Link
      to={to}
      className={cn(
        "inline-flex min-h-11 items-center justify-center gap-2 rounded-control font-medium transition-colors duration-fast ease-standard sm:min-h-0",
        FOCUS_RING,
        variantStyles[variant],
        sizeStyles[size],
        className,
      )}
    >
      {children}
    </Link>
  );
}
