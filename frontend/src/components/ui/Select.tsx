import { ChevronDown } from "lucide-react";
import { type SelectHTMLAttributes, forwardRef } from "react";

import { cn } from "@/lib/utils";

import { FieldError } from "./FieldError";
import { useFieldControl } from "./field-context";
import { controlClasses } from "./field-styles";

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  error?: string;
}

/** The native select (best keyboard and mobile behaviour) with the design's border and a chevron. */
export const Select = forwardRef<HTMLSelectElement, SelectProps>(({ className, error, children, ...props }, ref) => {
  const control = useFieldControl({ ...props, error });
  return (
    <div className="w-full">
      <div className="relative">
        <select
          ref={ref}
          className={cn(controlClasses(control.invalid, "appearance-none pr-9"), className)}
          {...props}
          id={control.id}
          aria-invalid={control.invalid || undefined}
          aria-describedby={control.describedBy}
        >
          {children}
        </select>
        <ChevronDown
          aria-hidden="true"
          className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-secondary"
        />
      </div>
      {error && control.ownErrorId && <FieldError id={control.ownErrorId}>{error}</FieldError>}
    </div>
  );
});
Select.displayName = "Select";
