import { AlertCircle } from "lucide-react";
import type { ReactNode } from "react";

export function ErrorState({ message = "Something went wrong.", action }: { message?: string; action?: ReactNode }) {
  return (
    <div role="alert" className="flex flex-col items-center justify-center gap-2 py-16 text-center">
      <AlertCircle aria-hidden="true" className="h-6 w-6 text-danger-fg" />
      <p className="text-sm font-medium text-danger-fg">{message}</p>
      {action}
    </div>
  );
}
