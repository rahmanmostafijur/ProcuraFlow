import { createContext, useId } from "react";
import { useContext } from "react";

export interface FieldContextValue {
  id: string;
  describedBy?: string;
  invalid: boolean;
  required: boolean;
}

/** Set by FormField so the control inside gets its id, aria-describedby and aria-invalid without wiring. */
export const FieldContext = createContext<FieldContextValue | null>(null);

interface ControlProps {
  id?: string;
  error?: string;
  "aria-describedby"?: string;
  "aria-invalid"?: boolean | "true" | "false" | "grammar" | "spelling";
  required?: boolean;
}

/**
 * Merge a control's own props with the surrounding FormField. A control used on its own with an `error` prop
 * still gets a described, invalid state and renders the message itself (`ownErrorId` is set only then).
 */
export function useFieldControl(props: ControlProps) {
  const field = useContext(FieldContext);
  const generated = useId();
  const id = props.id ?? field?.id ?? generated;
  const ownErrorId = props.error && !field ? `${id}-error` : undefined;
  const describedBy =
    [props["aria-describedby"], field?.describedBy, ownErrorId].filter(Boolean).join(" ") || undefined;
  const invalid =
    Boolean(props.error) ||
    Boolean(field?.invalid) ||
    props["aria-invalid"] === true ||
    props["aria-invalid"] === "true";
  return { id, ownErrorId, describedBy, invalid, required: props.required ?? field?.required };
}
