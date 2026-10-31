import {
  BarChart3,
  BookMarked,
  Building2,
  CheckSquare,
  ClipboardList,
  ClipboardPenLine,
  Banknote,
  Coins,
  Download,
  History,
  ShieldCheck,
  LayoutDashboard,
  Mail,
  Package,
  PiggyBank,
  Settings,
  SlidersHorizontal,
  Truck,
  Users,
  Warehouse,
} from "lucide-react";
import { NavLink } from "react-router-dom";

import { useApprovalQueue } from "@/api/approvals";
import { useCompanySettings } from "@/api/companySettings";
import { useAuth } from "@/lib/auth-context";

import { CompanyMark } from "./CompanyMark";
import { cn } from "@/lib/utils";

interface NavItem {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  permission?: string;
  /** Shown when the user holds at least one of these. */
  anyPermission?: string[];
  showsApprovalCount?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/suppliers", label: "Suppliers", icon: Building2 },
  { to: "/products", label: "Products", icon: Package },
  {
    to: "/requests",
    label: "Requests",
    icon: ClipboardPenLine,
    anyPermission: ["request:create", "request:read_all", "request:approve"],
  },
  { to: "/approvals", label: "Approvals", icon: CheckSquare, showsApprovalCount: true },
  { to: "/purchase-orders", label: "Purchase Orders", icon: ClipboardList },
  { to: "/catalog", label: "Catalog", icon: BookMarked },
  { to: "/budgets", label: "Budgets", icon: PiggyBank, permission: "budget:read" },
  { to: "/inventory", label: "Inventory", icon: Warehouse },
  { to: "/deliveries", label: "Deliveries", icon: Truck },
  { to: "/reports", label: "Reports", icon: BarChart3 },
  { to: "/audit-log", label: "Audit Log", icon: History, permission: "audit:read" },
  { to: "/payment-runs", label: "Payment runs", icon: Banknote, permission: "invoice:read" },
  { to: "/exports", label: "Exports", icon: Download, permission: "export:read" },
  { to: "/finance", label: "Currencies & tax", icon: Coins, permission: "finance:manage" },
  { to: "/approval-settings", label: "Approval settings", icon: SlidersHorizontal, permission: "approval:manage" },
  { to: "/users", label: "Users", icon: Users, permission: "user:manage" },
  { to: "/gdpr", label: "Personal data", icon: ShieldCheck, permission: "gdpr:manage" },
  { to: "/settings", label: "Settings", icon: Settings, permission: "settings:manage" },
  { to: "/settings/email-templates", label: "Email templates", icon: Mail, permission: "settings:manage" },
];

// Routes that are a prefix of another item's route, so only an exact match may highlight them.
const EXACT_MATCH_ROUTES = ["/", "/settings"];

const isVisible = (hasPermission: (code: string) => boolean) => (item: NavItem) =>
  (!item.permission || hasPermission(item.permission)) &&
  (!item.anyPermission || item.anyPermission.some(hasPermission));

export function Sidebar() {
  const { hasPermission } = useAuth();
  const { data: settings } = useCompanySettings();
  const { data: queue } = useApprovalQueue(1, 1);
  const waitingCount = queue?.total ?? 0;

  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-slate-200 bg-white">
      <div className="flex h-16 items-center border-b border-slate-200 px-5">
        <CompanyMark branding={settings} />
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {NAV_ITEMS.filter(isVisible(hasPermission)).map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={EXACT_MATCH_ROUTES.includes(item.to)}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900",
              )
            }
          >
            <item.icon className="h-4 w-4" />
            {item.label}
            {item.showsApprovalCount && waitingCount > 0 && (
              <span
                className="ml-auto rounded-full bg-brand-600 px-2 py-0.5 text-xs font-semibold text-white"
                aria-label={`${waitingCount} waiting for you`}
              >
                {waitingCount}
              </span>
            )}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
