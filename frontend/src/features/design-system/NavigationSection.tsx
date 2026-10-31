import { Button } from "@/components/ui/Button";
import { LifecycleStepper, type LifecycleStep } from "@/components/ui/LifecycleStepper";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Tabs } from "@/components/ui/Tabs";

import { Section, SubHeading, ThemePair } from "./showcase";

const STEPS: LifecycleStep[] = [
  { id: "draft", label: "Draft", state: "done", at: "2026-10-01" },
  { id: "submitted", label: "Submitted", state: "done", at: "2026-10-02" },
  { id: "approval", label: "Approval", state: "current", description: "Waiting for Finance" },
  { id: "ordered", label: "Ordered", state: "upcoming" },
  { id: "received", label: "Received", state: "upcoming" },
];

const REJECTED: LifecycleStep[] = [
  { id: "draft", label: "Draft", state: "done", at: "2026-10-01" },
  { id: "approval", label: "Approval", state: "rejected", description: "Over budget" },
  { id: "ordered", label: "Ordered", state: "upcoming" },
];

const TABS = [
  { id: "overview", label: "Overview", content: <p className="text-sm text-text-secondary">Summary of the order.</p> },
  {
    id: "lines",
    label: "Lines",
    badge: 12,
    content: <p className="text-sm text-text-secondary">Twelve line items.</p>,
  },
  { id: "files", label: "Files", content: <p className="text-sm text-text-secondary">Attachments.</p> },
  { id: "locked", label: "Locked", disabled: true, content: null },
];

export function NavigationSection() {
  return (
    <Section
      id="navigation"
      title="Tabs, stepper, page header and pagination"
      intro="Tabs use a roving tabindex: arrows move and select, Home and End jump. The stepper marks the current step with aria-current and spells out every state."
    >
      <ThemePair>
        <div className="space-y-8">
          <div>
            <SubHeading>Page header (one primary action)</SubHeading>

            <PageHeader
              title="Purchase orders"
              description="Everything you have ordered, by status."
              breadcrumbs={[{ label: "Buy", to: "/design-system" }, { label: "Purchase orders" }]}
              secondaryActions={<Button variant="secondary">Export</Button>}
              primaryAction={<Button>New order</Button>}
            />
          </div>
          <div>
            <SubHeading>Tabs: horizontal and vertical</SubHeading>
            <div className="grid gap-6 lg:grid-cols-2">
              <Tabs label="Order sections" tabs={TABS} />
              <Tabs label="Order sections (vertical)" tabs={TABS} orientation="vertical" />
            </div>
          </div>
          <div>
            <SubHeading>Lifecycle stepper: horizontal (stacks on small screens)</SubHeading>
            <LifecycleStepper steps={STEPS} label="Request progress" />
          </div>
          <div className="grid gap-6 lg:grid-cols-2">
            <div>
              <SubHeading>Vertical</SubHeading>
              <LifecycleStepper steps={STEPS} label="Request progress, vertical" orientation="vertical" />
            </div>
            <div>
              <SubHeading>Rejected</SubHeading>
              <LifecycleStepper steps={REJECTED} label="Rejected request progress" orientation="vertical" />
            </div>
          </div>
          <div>
            <SubHeading>Pagination</SubHeading>
            <Pagination page={2} pageSize={10} total={47} totalPages={5} onPageChange={() => undefined} />
          </div>
        </div>
      </ThemePair>
    </Section>
  );
}
