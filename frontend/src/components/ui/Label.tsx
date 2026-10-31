import type { ReactNode } from "react";

export function Label({ children, htmlFor, required }: { children: ReactNode; htmlFor?: string; required?: boolean }) {
  return (
    <label htmlFor={htmlFor} className="mb-1 block text-sm font-medium text-text-primary">
      {children}{" "}
      {required && (
        <span aria-hidden="true" className="text-danger-fg">
          *
        </span>
      )}
    </label>
  );
}
