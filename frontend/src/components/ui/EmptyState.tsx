import { Inbox, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Illustration } from "./Illustration";
import type { IllustrationName } from "./illustration-names";

export type { IllustrationName } from "./illustration-names";

interface EmptyStateProps {
  /** Legacy small icon; `illustration` takes precedence. */
  icon?: LucideIcon;
  illustration?: IllustrationName;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({ icon: Icon = Inbox, illustration, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
      {illustration ? (
        <Illustration name={illustration} />
      ) : (
        <Icon aria-hidden="true" className="h-10 w-10 text-text-muted" />
      )}
      <p className="text-sm font-semibold text-text-primary">{title}</p>
      {description && <p className="max-w-sm text-sm text-text-secondary">{description}</p>}
      {action}
    </div>
  );
}
