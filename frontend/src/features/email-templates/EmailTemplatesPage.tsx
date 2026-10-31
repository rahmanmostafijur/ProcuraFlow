import { useState } from "react";

import { useEmailTemplates } from "@/api/emailTemplates";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingState";
import { cn } from "@/lib/utils";

import { TemplateEditor } from "./TemplateEditor";

export function EmailTemplatesPage() {
  const { data: templates, isLoading, isError } = useEmailTemplates();
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  const selected = templates?.find((template) => template.key === selectedKey) ?? templates?.[0];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Email templates</h1>
        <p className="text-sm text-slate-500">The wording of the emails ProcuraFlow sends on your behalf.</p>
      </div>
      {isLoading && <LoadingState />}
      {isError && <ErrorState message="The templates could not be loaded. Reload the page to try again." />}
      {templates && selected && (
        <div className="grid gap-6 lg:grid-cols-[16rem_1fr]">
          <nav aria-label="Templates" className="space-y-1">
            {templates.map((template) => (
              <button
                key={template.key}
                type="button"
                aria-current={template.key === selected.key ? "true" : undefined}
                onClick={() => setSelectedKey(template.key)}
                className={cn(
                  "flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm font-medium",
                  template.key === selected.key
                    ? "bg-brand-50 text-brand-700"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900",
                )}
              >
                {template.label}
                {template.is_customised && <span className="text-xs font-normal text-slate-400">customised</span>}
              </button>
            ))}
          </nav>
          {/* Keyed so switching templates, or a saved change, starts the form from the stored values. */}
          <TemplateEditor key={`${selected.key}:${selected.subject}:${selected.body}`} template={selected} />
        </div>
      )}
    </div>
  );
}
