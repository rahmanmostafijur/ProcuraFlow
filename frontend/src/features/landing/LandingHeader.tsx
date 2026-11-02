import { Workflow } from "lucide-react";
import { Link } from "react-router-dom";

import { ThemeToggle } from "@/components/layout/ThemeToggle";
import { FOCUS_RING } from "@/components/ui/focus";
import { cn } from "@/lib/utils";

import { LandingLink } from "./LandingLink";

export function LandingHeader() {
  return (
    <header className="border-b border-border bg-surface">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <Link to="/" className={cn("inline-flex items-center gap-2 rounded-control", FOCUS_RING)}>
          <span className="flex h-8 w-8 items-center justify-center rounded-control bg-brand text-on-brand">
            <Workflow aria-hidden="true" className="h-5 w-5" />
          </span>
          <span className="text-title text-text-primary">ProcuraFlow</span>
        </Link>
        <nav aria-label="Account" className="flex items-center gap-2">
          <ThemeToggle />
          <LandingLink to="/login" variant="ghost" size="sm">
            Sign in
          </LandingLink>
          <LandingLink to="/login?demo=1" size="sm">
            Try the demo
          </LandingLink>
        </nav>
      </div>
    </header>
  );
}
