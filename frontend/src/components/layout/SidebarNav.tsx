import { NavLink } from "react-router-dom";

import { useApprovalQueue } from "@/api/approvals";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";

import { EXACT_MATCH_ROUTES, NAV_GROUPS, isNavItemVisible } from "./nav-config";

interface SidebarNavProps {
  /** Icons only; labels stay available to screen readers and as tooltips. */
  collapsed?: boolean;
  /** Called after a link is followed, so the mobile drawer can close itself. */
  onNavigate?: () => void;
}

export function SidebarNav({ collapsed = false, onNavigate }: SidebarNavProps) {
  const { hasPermission } = useAuth();
  const { data: queue } = useApprovalQueue(1, 1);
  const waitingCount = queue?.total ?? 0;

  const visible = isNavItemVisible(hasPermission);
  const groups = NAV_GROUPS.map((group) => ({ ...group, items: group.items.filter(visible) })).filter(
    (group) => group.items.length > 0,
  );

  return (
    <nav aria-label="Main" className="flex-1 space-y-4 overflow-y-auto px-2 py-4">
      {groups.map((group) => (
        <div key={group.id}>
          <p className={cn("mb-1 px-3 text-caption uppercase text-text-muted", collapsed && "sr-only")}>
            {group.label}
          </p>
          <div className="space-y-0.5">
            {group.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={EXACT_MATCH_ROUTES.includes(item.to)}
                title={collapsed ? item.label : undefined}
                onClick={onNavigate}
                className={({ isActive }) =>
                  cn(
                    "relative flex items-center gap-3 rounded-control px-3 py-2 text-sm font-medium transition-colors duration-fast ease-standard focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
                    isActive
                      ? "bg-brand-subtle text-brand-subtle-fg"
                      : "text-text-secondary hover:bg-bg hover:text-text-primary",
                  )
                }
              >
                <item.icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span className={cn(collapsed && "sr-only")}>{item.label}</span>
                {item.showsApprovalCount && waitingCount > 0 && (
                  <span
                    className={cn(
                      "rounded-full bg-brand px-2 py-0.5 text-xs font-semibold tabular-nums text-on-brand",
                      collapsed ? "absolute right-1 top-1 px-1.5 py-0 text-[10px]" : "ml-auto",
                    )}
                    aria-label={`${waitingCount} waiting for you`}
                  >
                    {waitingCount}
                  </span>
                )}
              </NavLink>
            ))}
          </div>
        </div>
      ))}
    </nav>
  );
}
