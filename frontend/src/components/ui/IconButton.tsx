import { type ButtonHTMLAttributes, type ReactNode, forwardRef } from "react";

import { cn } from "@/lib/utils";

import type { ButtonVariant } from "./Button";
import { variantStyles } from "./button-styles";
import { FOCUS_RING } from "./focus";
import { Spinner } from "./Spinner";

interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "aria-label" | "children"> {
  /** Required: an icon has no text, so the accessible name must be given. */
  "aria-label": string;
  icon: ReactNode;
  variant?: ButtonVariant;
  size?: "sm" | "md" | "lg";
  loading?: boolean;
}

const SIZES = { sm: "h-8 w-8", md: "h-10 w-10", lg: "h-12 w-12" } as const;

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  ({ icon, variant = "ghost", size = "md", loading = false, className, disabled, title, ...props }, ref) => (
    <button
      ref={ref}
      type="button"
      title={title ?? props["aria-label"]}
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-control transition-colors duration-fast ease-standard disabled:cursor-not-allowed disabled:opacity-50 max-sm:min-h-11 max-sm:min-w-11",
        FOCUS_RING,
        variantStyles[variant],
        SIZES[size],
        className,
      )}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading ? <Spinner /> : <span aria-hidden="true">{icon}</span>}
    </button>
  ),
);
IconButton.displayName = "IconButton";
