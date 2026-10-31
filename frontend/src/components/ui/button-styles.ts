import type { ButtonSize, ButtonVariant } from "./Button";

export const variantStyles: Record<ButtonVariant, string> = {
  primary: "bg-brand text-on-brand hover:bg-brand-hover",
  secondary: "border border-border-strong bg-surface text-text-primary hover:bg-bg",
  danger: "bg-danger-solid text-danger-on hover:opacity-90",
  ghost: "bg-transparent text-text-secondary hover:bg-bg hover:text-text-primary",
};

export const sizeStyles: Record<ButtonSize, string> = {
  sm: "px-2.5 py-1.5 text-sm",
  md: "px-4 py-2 text-sm",
  lg: "px-5 py-2.5 text-body",
};
