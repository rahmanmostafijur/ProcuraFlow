import { type ButtonHTMLAttributes, type ReactNode, forwardRef } from "react";

import { cn } from "@/lib/utils";

import { FOCUS_RING } from "./focus";
import { sizeStyles, variantStyles } from "./button-styles";
import { Spinner } from "./Spinner";

export type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Shows a spinner, sets aria-busy and blocks clicks. The label stays so the width does not jump. */
  loading?: boolean;
  leadingIcon?: ReactNode;
}

// 44 px touch targets on narrow screens (WCAG 2.5.8 and the design doc); desktop keeps the compact size.
const TOUCH = "max-sm:min-h-11";

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    { className, variant = "primary", size = "md", loading = false, leadingIcon, disabled, children, ...props },
    ref,
  ) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-control font-medium transition-colors duration-fast ease-standard disabled:cursor-not-allowed disabled:opacity-50",
        FOCUS_RING,
        TOUCH,
        variantStyles[variant],
        sizeStyles[size],
        className,
      )}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading ? <Spinner /> : leadingIcon}
      {children}
    </button>
  ),
);
Button.displayName = "Button";
