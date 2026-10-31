import { CommandPalette } from "@/components/ui/CommandPalette";
import { RadioGroup } from "@/components/ui/Radio";
import { ShortcutHelp } from "@/components/ui/ShortcutHelp";
import { ShortcutProvider } from "@/components/ui/ShortcutProvider";
import { useShortcut } from "@/components/ui/shortcuts-context";
import { useToast } from "@/components/ui/toast-context";
import { type ThemeMode, useTheme } from "@/lib/theme";

import { ButtonsSection } from "./ButtonsSection";
import { ChartsSection } from "./ChartsSection";
import { DataSection } from "./DataSection";
import { DocumentSection } from "./DocumentSection";
import { FeedbackSection } from "./FeedbackSection";
import { FormsSection } from "./FormsSection";
import { mockSearch } from "./mock-data";
import { NavigationSection } from "./NavigationSection";
import { OverlaysSection } from "./OverlaysSection";
import { TableOfContents, type TocEntry } from "./showcase";

// Unique string the production build check greps for: it must never appear in dist/.
const DESIGN_SYSTEM_MARKER = "pf-design-system-marker-7f3a9c";

const SECTIONS: TocEntry[] = [
  { id: "buttons", label: "Buttons" },
  { id: "forms", label: "Form controls" },
  { id: "data", label: "Status, KPIs, data table" },
  { id: "charts", label: "Charts" },
  { id: "feedback", label: "Empty, loading, toasts" },
  { id: "overlays", label: "Dialogs and palette" },
  { id: "navigation", label: "Tabs, stepper, header" },
  { id: "documents", label: "Timeline, diff, upload" },
];

const THEME_OPTIONS: Array<{ value: ThemeMode; label: string }> = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "System" },
];

function Palette() {
  const { toast } = useToast();
  useShortcut({
    keys: "g d",
    description: "Go to dashboard (demo)",
    group: "Navigation",
    handler: () => toast({ message: "Would go to the dashboard", type: "info" }),
  });
  return (
    <>
      <CommandPalette
        search={mockSearch}
        onSelectItem={(item) => toast({ message: `Would open ${item.label}`, type: "info" })}
        actions={[
          {
            id: "new-po",
            label: "Create purchase order",
            keywords: ["buy", "new"],
            run: () => toast({ message: "Would create an order" }),
          },
          {
            id: "new-request",
            label: "Create purchase request",
            keywords: ["buy", "new"],
            run: () => toast({ message: "Would create a request" }),
          },
        ]}
      />
      <ShortcutHelp />
    </>
  );
}

function ThemeSwitch() {
  const { mode, setMode, resolved } = useTheme();
  return (
    <div className="space-y-1">
      <RadioGroup
        legend="Page theme"
        orientation="horizontal"
        value={mode}
        onChange={(value) => setMode(value as ThemeMode)}
        options={THEME_OPTIONS}
      />
      <p className="text-xs text-text-secondary">Showing {resolved}. Each block below also has a forced dark copy.</p>
    </div>
  );
}

/** Dev-only. App.tsx only mounts this when import.meta.env.DEV is true. */
export function DesignSystemPage() {
  return (
    <ShortcutProvider>
      <div data-design-system={DESIGN_SYSTEM_MARKER} className="min-h-full bg-bg text-text-primary">
        <header className="border-b border-border bg-surface px-6 py-5">
          <div className="mx-auto flex max-w-7xl flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-display-md text-text-primary">ProcuraFlow design system</h1>
              <p className="mt-1 max-w-2xl text-body text-text-secondary">
                Every component in every state, in light and dark. Development only: this page is not part of the
                production build.
              </p>
            </div>
            <ThemeSwitch />
          </div>
        </header>
        <div className="mx-auto flex max-w-7xl gap-8 px-6 py-8">
          <aside className="hidden w-52 shrink-0 lg:block">
            <div className="sticky top-6">
              <TableOfContents entries={SECTIONS} />
            </div>
          </aside>
          <main className="min-w-0 flex-1 space-y-14">
            <div className="lg:hidden">
              <TableOfContents entries={SECTIONS} />
            </div>
            <ButtonsSection />
            <FormsSection />
            <DataSection />
            <ChartsSection />
            <FeedbackSection />
            <OverlaysSection />
            <NavigationSection />
            <DocumentSection />
          </main>
        </div>
        <Palette />
      </div>
    </ShortcutProvider>
  );
}
