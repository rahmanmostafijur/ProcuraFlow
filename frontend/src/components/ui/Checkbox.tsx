import { type InputHTMLAttributes, type ReactNode, forwardRef, useEffect, useImperativeHandle, useRef } from "react";

import { cn } from "@/lib/utils";

import { FOCUS_RING } from "./focus";

interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label?: ReactNode;
  hint?: ReactNode;
  /** Mixed state for "select all"; reflected as aria-checked="mixed" by the browser. */
  indeterminate?: boolean;
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(
  ({ label, hint, indeterminate = false, className, id, ...props }, ref) => {
    const inner = useRef<HTMLInputElement>(null);
    useImperativeHandle(ref, () => inner.current!);
    useEffect(() => {
      if (inner.current) inner.current.indeterminate = indeterminate;
    }, [indeterminate]);

    const box = (
      <input
        ref={inner}
        id={id}
        type="checkbox"
        className={cn(
          "h-4 w-4 shrink-0 cursor-pointer rounded-sm border-border-strong accent-brand disabled:cursor-not-allowed disabled:opacity-60",
          FOCUS_RING,
          className,
        )}
        {...props}
      />
    );
    if (!label) return box;
    return (
      <label className="inline-flex items-start gap-2 text-sm text-text-primary">
        <span className="mt-0.5 inline-flex">{box}</span>
        <span>
          {label}
          {hint && <span className="block text-xs text-text-secondary">{hint}</span>}
        </span>
      </label>
    );
  },
);
Checkbox.displayName = "Checkbox";
