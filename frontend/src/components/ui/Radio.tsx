import { type InputHTMLAttributes, type ReactNode, forwardRef, useId } from "react";

import { cn } from "@/lib/utils";

import { FOCUS_RING } from "./focus";

interface RadioProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label: ReactNode;
  hint?: ReactNode;
}

export const Radio = forwardRef<HTMLInputElement, RadioProps>(({ label, hint, className, ...props }, ref) => (
  <label className="inline-flex items-start gap-2 text-sm text-text-primary">
    <input
      ref={ref}
      type="radio"
      className={cn(
        "mt-0.5 h-4 w-4 shrink-0 cursor-pointer accent-brand disabled:cursor-not-allowed disabled:opacity-60",
        FOCUS_RING,
        className,
      )}
      {...props}
    />
    <span>
      {label}
      {hint && <span className="block text-xs text-text-secondary">{hint}</span>}
    </span>
  </label>
));
Radio.displayName = "Radio";

export interface RadioOption {
  value: string;
  label: ReactNode;
  hint?: ReactNode;
  disabled?: boolean;
}

interface RadioGroupProps {
  legend: string;
  options: RadioOption[];
  value: string;
  onChange: (value: string) => void;
  name?: string;
  orientation?: "vertical" | "horizontal";
}

/** A fieldset with a legend; native radios give arrow-key movement and a single tab stop for free. */
export function RadioGroup({ legend, options, value, onChange, name, orientation = "vertical" }: RadioGroupProps) {
  const generated = useId();
  return (
    <fieldset>
      <legend className="mb-1 text-sm font-medium text-text-primary">{legend}</legend>
      <div className={cn("flex gap-3", orientation === "vertical" ? "flex-col" : "flex-row flex-wrap gap-x-6")}>
        {options.map((option) => (
          <Radio
            key={option.value}
            name={name ?? generated}
            value={option.value}
            label={option.label}
            hint={option.hint}
            disabled={option.disabled}
            checked={value === option.value}
            onChange={() => onChange(option.value)}
          />
        ))}
      </div>
    </fieldset>
  );
}
