import {
  Banknote,
  BarChart3,
  BookMarked,
  Building2,
  CheckSquare,
  ClipboardList,
  ClipboardPenLine,
  Coins,
  Download,
  FileText,
  History,
  LayoutDashboard,
  Mail,
  Package,
  PiggyBank,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Truck,
  Users,
  Warehouse,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  permission?: string;
  /** Shown when the user holds at least one of these. */
  anyPermission?: string[];
  showsApprovalCount?: boolean;
}

export interface NavGroup {
  id: string;
  label: string;
  items: NavItem[];
}

/** Grouped by where the work sits in the request-to-paid flow. */
export const NAV_GROUPS: NavGroup[] = [
  {
    id: "overview",
    label: "Overview",
    items: [{ to: "/", label: "Dashboard", icon: LayoutDashboard }],
  },
  {
    id: "buy",
    label: "Buy",
    items: [
      {
        to: "/requests",
        label: "Requests",
        icon: ClipboardPenLine,
        anyPermission: ["request:create", "request:read_all", "request:approve"],
      },
      { to: "/approvals", label: "Approvals", icon: CheckSquare, showsApprovalCount: true },
      { to: "/purchase-orders", label: "Purchase Orders", icon: ClipboardList },
      { to: "/catalog", label: "Catalog", icon: BookMarked },
    ],
  },
  {
    id: "receive",
    label: "Receive and pay",
    items: [
      { to: "/deliveries", label: "Deliveries", icon: Truck },
      { to: "/inventory", label: "Inventory", icon: Warehouse },
      { to: "/invoices", label: "Invoices", icon: FileText, permission: "invoice:read" },
      { to: "/payment-runs", label: "Payment runs", icon: Banknote, permission: "invoice:read" },
    ],
  },
  {
    id: "master",
    label: "Master data",
    items: [
      { to: "/suppliers", label: "Suppliers", icon: Building2 },
      { to: "/products", label: "Products", icon: Package },
      { to: "/budgets", label: "Budgets", icon: PiggyBank, permission: "budget:read" },
    ],
  },
  {
    id: "insight",
    label: "Insight",
    items: [
      { to: "/reports", label: "Reports", icon: BarChart3 },
      { to: "/exports", label: "Exports", icon: Download, permission: "export:read" },
      { to: "/audit-log", label: "Audit Log", icon: History, permission: "audit:read" },
    ],
  },
  {
    id: "admin",
    label: "Administration",
    items: [
      { to: "/finance", label: "Currencies & tax", icon: Coins, permission: "finance:manage" },
      { to: "/approval-settings", label: "Approval settings", icon: SlidersHorizontal, permission: "approval:manage" },
      { to: "/users", label: "Users", icon: Users, permission: "user:manage" },
      { to: "/gdpr", label: "Personal data", icon: ShieldCheck, permission: "gdpr:manage" },
      { to: "/settings", label: "Settings", icon: Settings, permission: "settings:manage" },
      { to: "/settings/email-templates", label: "Email templates", icon: Mail, permission: "settings:manage" },
    ],
  },
];

// Routes that are a prefix of another item's route, so only an exact match may highlight them.
export const EXACT_MATCH_ROUTES = ["/", "/settings"];

export const isNavItemVisible = (hasPermission: (code: string) => boolean) => (item: NavItem) =>
  (!item.permission || hasPermission(item.permission)) &&
  (!item.anyPermission || item.anyPermission.some(hasPermission));
