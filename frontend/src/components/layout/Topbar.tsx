import { LogOut } from "lucide-react";

import { Link } from "react-router-dom";

import { Button } from "@/components/ui/Button";
import { useAuth } from "@/lib/auth-context";

import { NotificationBell } from "./NotificationBell";

export function Topbar() {
  const { user, logout } = useAuth();

  return (
    <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-6">
      <div />
      <div className="flex items-center gap-4">
        <NotificationBell />
        <Link to="/profile" aria-label="Your profile" className="rounded-md text-right hover:bg-slate-50">
          <p className="text-sm font-medium text-slate-900">{user?.full_name}</p>
          <p className="text-xs capitalize text-slate-500">{user?.role.name.replace(/_/g, " ")}</p>
        </Link>
        <Button variant="ghost" size="sm" onClick={logout}>
          <LogOut className="h-4 w-4" /> Sign out
        </Button>
      </div>
    </header>
  );
}
