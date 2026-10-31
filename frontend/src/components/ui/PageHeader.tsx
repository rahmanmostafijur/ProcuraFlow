import { ChevronRight } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

export interface Breadcrumb {
  label: string;
  /** Omit on the current page. */
  to?: string;
}

interface PageHeaderProps {
  title: string;
  description?: string;
  breadcrumbs?: Breadcrumb[];
  /** The single primary action of the view (design rule: one per page). */
  primaryAction?: ReactNode;
  /** Quiet buttons that sit beside it. */
  secondaryActions?: ReactNode;
}

export function PageHeader({ title, description, breadcrumbs, primaryAction, secondaryActions }: PageHeaderProps) {
  return (
    <header className="mb-6 space-y-2">
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav aria-label="Breadcrumb">
          <ol className="flex flex-wrap items-center gap-1 text-sm text-text-secondary">
            {breadcrumbs.map((crumb, index) => (
              <li key={`${crumb.label}-${index}`} className="flex items-center gap-1">
                {index > 0 && <ChevronRight aria-hidden="true" className="h-3.5 w-3.5" />}
                {crumb.to ? (
                  <Link
                    to={crumb.to}
                    className="rounded-control underline-offset-2 hover:text-text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
                  >
                    {crumb.label}
                  </Link>
                ) : (
                  <span aria-current="page" className="text-text-primary">
                    {crumb.label}
                  </span>
                )}
              </li>
            ))}
          </ol>
        </nav>
      )}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-display-md text-text-primary">{title}</h1>
          {description && <p className="mt-1 text-body text-text-secondary">{description}</p>}
        </div>
        {(primaryAction || secondaryActions) && (
          <div className="flex flex-wrap items-center gap-2">
            {secondaryActions}
            {primaryAction}
          </div>
        )}
      </div>
    </header>
  );
}
