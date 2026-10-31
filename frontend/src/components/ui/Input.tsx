import { type InputHTMLAttributes, forwardRef } from "react";

import { cn } from "@/lib/utils";

import { FieldError } from "./FieldError";
import { useFieldControl } from "./field-context";
import { controlClasses } from "./field-styles";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(({ className, error, ...props }, ref) => {
  const control = useFieldControl({ ...props, error });
  return (
    <div className="w-full">
      <input
        ref={ref}
        className={cn(controlClasses(control.invalid), className)}
        // Most inputs here hold business records, which browsers must not autofill with personal data.
        // A caller that wants autofill (the login form) passes its own value.
        autoComplete="off"
        {...props}
        id={control.id}
        aria-invalid={control.invalid || undefined}
        aria-describedby={control.describedBy}
      />
      {error && control.ownErrorId && <FieldError id={control.ownErrorId}>{error}</FieldError>}
    </div>
  );
});
Input.displayName = "Input";
