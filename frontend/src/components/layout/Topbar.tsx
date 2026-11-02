import { LogOut, Menu, Search } from "lucide-react";
import { Link } from "react-router-dom";

import { IconButton } from "@/components/ui/IconButton";
import { useAuth } from "@/lib/auth-context";

import { NotificationBell } from "./NotificationBell";
import { ThemeToggle } from "./ThemeToggle";

interface TopbarProps {
  onOpenSearch: () => void;
  onOpenMenu: () => void;
}

export function Topbar({ onOpenSearch, onOpenMenu }: TopbarProps) {
  const { user, logout } = useAuth();

  return (
    <header className="flex h-16 shrink-0 items-center gap-3 border-b border-border bg-surface px-4 md:px-6">
      <IconButton
        aria-label="Open navigation"
        className="md:hidden"
        icon={<Menu className="h-5 w-5" />}
        onClick={onOpenMenu}
      />
      <button
        type="button"
        onClick={onOpenSearch}
        className="flex h-10 min-w-0 flex-1 items-center gap-2 rounded-control border border-border bg-bg px-3 text-left text-sm text-text-secondary transition-colors duration-fast hover:border-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus md:max-w-md"
      >
        <Search className="h-4 w-4 shrink-0" aria-hidden="true" />
        <span className="flex-1 truncate">Search everything</span>
        <kbd className="hidden rounded border border-border px-1.5 text-xs sm:inline">Ctrl K</kbd>
      </button>
      <div className="ml-auto flex items-center gap-1 sm:gap-2">
        <ThemeToggle />
        <NotificationBell />
        <Link
          to="/profile"
          aria-label="Your profile"
          className="hidden rounded-control px-2 py-1 text-right hover:bg-bg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus lg:block"
        >
          <p className="text-sm font-medium text-text-primary">{user?.full_name}</p>
          <p className="text-xs capitalize text-text-secondary">{user?.role.name.replace(/_/g, " ")}</p>
        </Link>
        <IconButton aria-label="Sign out" icon={<LogOut className="h-4 w-4" />} onClick={logout} />
      </div>
    </header>
  );
}
