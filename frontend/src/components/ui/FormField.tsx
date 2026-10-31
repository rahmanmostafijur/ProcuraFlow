import { type ReactNode, useId, useMemo } from "react";

import { FieldContext } from "./field-context";
import { FieldError } from "./FieldError";

interface FormFieldProps {
  label: string;
  children: ReactNode;
  hint?: string;
  error?: string;
  required?: boolean;
}

/**
 * Label + control + hint + error. The control (Input, Textarea, Select, Combobox) reads the id and aria wiring from
 * context, so the label is tied by `for`, and hint/error by aria-describedby; an error also sets aria-invalid.
 */
export function FormField({ label, children, hint, error, required }: FormFieldProps) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const value = useMemo(
    () => ({
      id,
      describedBy: [hintId, errorId].filter(Boolean).join(" ") || undefined,
      invalid: Boolean(error),
      required: Boolean(required),
    }),
    [id, hintId, errorId, error, required],
  );
  return (
    <div className="w-full">
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-text-primary">
        {label}
        {required && (
          <span aria-hidden="true" className="ml-0.5 text-danger-fg">
            *
          </span>
        )}
      </label>
      <FieldContext.Provider value={value}>{children}</FieldContext.Provider>
      {hint && (
        <p id={hintId} className="mt-1 text-xs text-text-secondary">
          {hint}
        </p>
      )}
      {error && <FieldError id={errorId}>{error}</FieldError>}
    </div>
  );
}
