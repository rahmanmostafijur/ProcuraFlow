import { AlertCircle } from "lucide-react";

/** Error message with an icon so the state is not conveyed by colour alone. role=alert announces it when it appears. */
export function FieldError({ id, children }: { id?: string; children: string }) {
  return (
    <p id={id} role="alert" className="mt-1 flex items-start gap-1 text-xs font-medium text-danger-fg">
      <AlertCircle aria-hidden="true" className="mt-px h-3.5 w-3.5 shrink-0" />
      {children}
    </p>
  );
}
