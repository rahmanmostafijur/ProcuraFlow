import { type TextareaHTMLAttributes, forwardRef } from "react";

import { cn } from "@/lib/utils";

import { FieldError } from "./FieldError";
import { useFieldControl } from "./field-context";
import { controlClasses } from "./field-styles";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(({ className, error, ...props }, ref) => {
  const control = useFieldControl({ ...props, error });
  return (
    <div className="w-full">
      <textarea
        ref={ref}
        className={cn(controlClasses(control.invalid), className)}
        {...props}
        id={control.id}
        aria-invalid={control.invalid || undefined}
        aria-describedby={control.describedBy}
      />
      {error && control.ownErrorId && <FieldError id={control.ownErrorId}>{error}</FieldError>}
    </div>
  );
});
Textarea.displayName = "Textarea";
