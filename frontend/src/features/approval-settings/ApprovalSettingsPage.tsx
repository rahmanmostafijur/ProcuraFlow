import { LimitsSection } from "./LimitsSection";
import { RulesSection } from "./RulesSection";

export function ApprovalSettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Approval settings</h1>
        <p className="text-sm text-slate-500">Who must approve what, by amount.</p>
      </div>
      <RulesSection />
      <LimitsSection />
    </div>
  );
}
