import { Check } from "lucide-react";
import { type ButtonHTMLAttributes, useId } from "react";

import { cn } from "@/lib/utils";

import { FOCUS_RING } from "./focus";

interface SwitchProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "onChange" | "role" | "children"> {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  hint?: string;
}

/** A button with role=switch: Space and Enter toggle it. The check mark in the thumb says "on" without colour. */
export function Switch({ checked, onChange, label, hint, disabled, className, id, ...props }: SwitchProps) {
  const generated = useId();
  const buttonId = id ?? generated;
  return (
    <div className="flex items-start gap-3">
      <button
        {...props}
        id={buttonId}
        type="button"
        role="switch"
        aria-checked={checked}
        aria-describedby={hint ? `${buttonId}-hint` : undefined}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border-2 transition-colors duration-fast ease-standard disabled:cursor-not-allowed disabled:opacity-60",
          FOCUS_RING,
          checked ? "border-brand bg-brand" : "border-border-strong bg-surface",
          className,
        )}
      >
        <span
          aria-hidden="true"
          className={cn(
            "inline-flex h-4 w-4 items-center justify-center rounded-full transition-transform duration-fast ease-standard",
            checked ? "translate-x-5 bg-on-brand text-brand" : "translate-x-0.5 bg-border-strong text-surface",
          )}
        >
          {checked && <Check className="h-3 w-3" strokeWidth={3} />}
        </span>
      </button>
      <label htmlFor={buttonId} className="text-sm text-text-primary">
        {label}
        {hint && (
          <span id={`${buttonId}-hint`} className="block text-xs text-text-secondary">
            {hint}
          </span>
        )}
      </label>
    </div>
  );
}
