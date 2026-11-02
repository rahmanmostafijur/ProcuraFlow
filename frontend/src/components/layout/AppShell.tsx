import { Suspense, useMemo, useState } from "react";
import { Outlet, useNavigate } from "react-router-dom";

import { searchEverything } from "@/api/search";
import { CommandPalette } from "@/components/ui/CommandPalette";
import type { PaletteAction } from "@/components/ui/command-palette/palette-types";
import { Drawer } from "@/components/ui/Drawer";
import { LoadingState } from "@/components/ui/LoadingState";
import { ShortcutHelp } from "@/components/ui/ShortcutHelp";
import { ShortcutProvider } from "@/components/ui/ShortcutProvider";
import { useAuth } from "@/lib/auth-context";

import { NAV_GROUPS, isNavItemVisible } from "./nav-config";
import { Sidebar } from "./Sidebar";
import { SidebarNav } from "./SidebarNav";
import { Topbar } from "./Topbar";

export function AppShell() {
  return (
    <ShortcutProvider>
      <Shell />
    </ShortcutProvider>
  );
}

function Shell() {
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  // Every page the user may open is a palette action, so the palette doubles as quick navigation.
  const actions = useMemo<PaletteAction[]>(
    () =>
      NAV_GROUPS.flatMap((group) => group.items.filter(isNavItemVisible(hasPermission))).map((item) => ({
        id: `go-${item.to}`,
        label: `Go to ${item.label}`,
        keywords: [item.label],
        run: () => navigate(item.to),
      })),
    [hasPermission, navigate],
  );

  return (
    <div className="flex h-screen bg-bg text-text-primary">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-control focus:bg-surface focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <Sidebar />
      <Drawer isOpen={menuOpen} onClose={() => setMenuOpen(false)} title="Navigation" side="left">
        <SidebarNav onNavigate={() => setMenuOpen(false)} />
      </Drawer>
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <Topbar onOpenSearch={() => setPaletteOpen(true)} onOpenMenu={() => setMenuOpen(true)} />
        <main id="main" tabIndex={-1} className="flex-1 overflow-y-auto p-4 focus:outline-none md:p-6">
          <Suspense fallback={<LoadingState />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
      <CommandPalette
        search={searchEverything}
        actions={actions}
        isOpen={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onSelectItem={(item) => {
          setPaletteOpen(false);
          if (item.href) void navigate(item.href);
        }}
      />
      <ShortcutHelp />
    </div>
  );
}
