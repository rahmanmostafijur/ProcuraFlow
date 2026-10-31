import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Divider } from "@/components/ui/Divider";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { ILLUSTRATION_NAMES } from "@/components/ui/illustration-names";
import { LoadingState } from "@/components/ui/LoadingState";
import { Skeleton, SkeletonText } from "@/components/ui/Skeleton";
import { Spinner } from "@/components/ui/Spinner";
import { Stat } from "@/components/ui/Stat";
import { useToast } from "@/components/ui/toast-context";

import { Section, SubHeading, ThemePair } from "./showcase";

const COPY: Record<(typeof ILLUSTRATION_NAMES)[number], [string, string]> = {
  inbox: ["Nothing to review", "New items will appear here."],
  search: ["No results", "Try a different search term."],
  documents: ["No documents yet", "Attach the first one to get started."],
  orders: ["No purchase orders", "Create an order from an approved request."],
  approvals: ["You are all caught up", "No approvals are waiting for you."],
  suppliers: ["No suppliers", "Add a supplier to start ordering."],
  files: ["No files uploaded", "Drop files here or choose them."],
  error: ["Could not load this", "Check your connection and try again."],
};

function ToastButtons() {
  const { toast } = useToast();
  return (
    <div className="flex flex-wrap gap-2">
      <Button variant="secondary" onClick={() => toast({ message: "Purchase order approved", type: "success" })}>
        Success toast
      </Button>
      <Button variant="secondary" onClick={() => toast({ message: "3 invoices are due this week", type: "info" })}>
        Info toast
      </Button>
      <Button
        variant="secondary"
        onClick={() => toast({ title: "Budget at 92%", message: "Facilities is close to its limit.", type: "warning" })}
      >
        Warning toast
      </Button>
      <Button
        variant="secondary"
        onClick={() => toast({ message: "Payment file could not be created", type: "error" })}
      >
        Error toast (assertive)
      </Button>
      <Button
        variant="secondary"
        onClick={() =>
          toast({ message: "Supplier deleted", durationMs: 0, action: { label: "Undo", onClick: () => undefined } })
        }
      >
        Sticky with action
      </Button>
    </div>
  );
}

export function FeedbackSection() {
  return (
    <Section
      id="feedback"
      title="Empty, loading and feedback"
      intro="Eight original illustrations share one line-and-fill style and are decorative (aria-hidden). Toasts stack bottom right; hover or focus pauses the timer, errors are announced assertively."
    >
      <div>
        <SubHeading>Toasts (hover one to pause it)</SubHeading>
        <ToastButtons />
      </div>
      <ThemePair>
        <div className="space-y-8">
          <div>
            <SubHeading>Empty states</SubHeading>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {ILLUSTRATION_NAMES.map((name) => (
                <Card key={name} padding="md">
                  <EmptyState
                    illustration={name}
                    title={COPY[name][0]}
                    description={COPY[name][1]}
                    action={<Button size="sm">Primary action</Button>}
                  />
                </Card>
              ))}
            </div>
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            <Card padding="md">
              <SubHeading>Loading</SubHeading>
              <LoadingState label="Loading orders…" />
              <div className="flex items-center gap-3">
                <Spinner className="text-brand" /> <Spinner className="h-6 w-6 text-text-secondary" />
              </div>
            </Card>
            <Card padding="md">
              <SubHeading>Skeleton</SubHeading>
              <div role="status" aria-busy="true" className="space-y-3">
                <span className="sr-only">Loading content</span>
                <Skeleton className="h-8 w-40" />
                <SkeletonText lines={3} />
              </div>
            </Card>
            <Card padding="md">
              <SubHeading>Error</SubHeading>
              <ErrorState
                message="Could not load purchase orders."
                action={
                  <Button size="sm" variant="secondary">
                    Try again
                  </Button>
                }
              />
            </Card>
          </div>
          <Card padding="md">
            <SubHeading>Stat, card, divider</SubHeading>
            <div className="flex flex-wrap items-center gap-6">
              <Stat label="Open orders" value="42" hint="3 overdue" />
              <Divider orientation="vertical" className="h-12" />
              <Stat label="Average approval time" value="1.8 days" />
            </div>
          </Card>
        </div>
      </ThemePair>
    </Section>
  );
}
