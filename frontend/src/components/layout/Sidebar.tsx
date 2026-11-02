import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { useState } from "react";

import { useCompanySettings } from "@/api/companySettings";
import { IconButton } from "@/components/ui/IconButton";
import { cn } from "@/lib/utils";

import { CompanyMark } from "./CompanyMark";
import { SidebarNav } from "./SidebarNav";

const COLLAPSED_KEY = "pf-sidebar-collapsed";

// Storage can throw (private windows, blocked site data), so the sidebar must work without it.
function readCollapsed(): boolean {
  try {
    return window.localStorage.getItem(COLLAPSED_KEY) === "1";
  } catch {
    return false;
  }
}

function writeCollapsed(collapsed: boolean): void {
  try {
    window.localStorage.setItem(COLLAPSED_KEY, collapsed ? "1" : "0");
  } catch {
    // Not persisted; the choice still applies for this page view.
  }
}

/** The desktop sidebar. Below the md breakpoint the Topbar opens the same navigation in a drawer. */
export function Sidebar() {
  const { data: settings } = useCompanySettings();
  const [collapsed, setCollapsed] = useState(readCollapsed);

  const toggle = () => {
    writeCollapsed(!collapsed);
    setCollapsed(!collapsed);
  };

  return (
    <aside
      className={cn(
        "hidden h-full shrink-0 flex-col border-r border-border bg-surface transition-[width] duration-base ease-standard md:flex",
        collapsed ? "w-16" : "w-60",
      )}
    >
      <div className="flex h-16 items-center justify-between gap-2 border-b border-border px-3">
        <div className={cn("min-w-0 pl-2", collapsed && "sr-only")}>
          <CompanyMark branding={settings} />
        </div>
        <IconButton
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!collapsed}
          size="sm"
          icon={collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          onClick={toggle}
        />
      </div>
      <SidebarNav collapsed={collapsed} />
    </aside>
  );
}
