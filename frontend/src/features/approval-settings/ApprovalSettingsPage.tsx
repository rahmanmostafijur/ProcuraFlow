import { PageHeader } from "@/components/ui/PageHeader";

import { LimitsSection } from "./LimitsSection";
import { RulesSection } from "./RulesSection";

export function ApprovalSettingsPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="Approval settings" description="Who must approve what, by amount." />
      <RulesSection />
      <LimitsSection />
    </div>
  );
}
