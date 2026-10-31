import { LogOut } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import { useBranding } from "@/api/companySettings";
import { CompanyMark } from "@/components/layout/CompanyMark";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";
import { useApplyBrandColor } from "@/lib/use-brand-color";

const NAV_ITEMS = [
  { to: "/portal", label: "Orders", end: true },
  { to: "/portal/invoices", label: "Invoices", end: false },
  { to: "/portal/documents", label: "Documents", end: false },
  { to: "/portal/password", label: "Password", end: false },
];

/** The supplier's own, simpler area. It never loads internal data: only the public branding and /portal calls. */
export function PortalShell() {
  const { user, logout } = useAuth();
  const { data: branding } = useBranding();
  useApplyBrandColor(branding?.brand_color);

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-16 max-w-5xl items-center justify-between px-6">
          <CompanyMark branding={branding} />
          <div className="flex items-center gap-4">
            <span className="text-sm text-slate-600">{user?.full_name}</span>
            <Button variant="ghost" size="sm" onClick={logout}>
              <LogOut className="h-4 w-4" /> Sign out
            </Button>
          </div>
        </div>
        <nav aria-label="Supplier portal" className="mx-auto flex max-w-5xl gap-1 px-6">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  "border-b-2 px-3 py-2 text-sm font-medium",
                  isActive
                    ? "border-brand-600 text-brand-700"
                    : "border-transparent text-slate-600 hover:text-slate-900",
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="mx-auto max-w-5xl p-6">
        <Outlet />
      </main>
    </div>
  );
}
