import { useState } from "react";

import { useEmailTemplates } from "@/api/emailTemplates";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingState";
import { PageHeader } from "@/components/ui/PageHeader";
import { cn } from "@/lib/utils";

import { TemplateEditor } from "./TemplateEditor";

export function EmailTemplatesPage() {
  const { data: templates, isLoading, isError } = useEmailTemplates();
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  const selected = templates?.find((template) => template.key === selectedKey) ?? templates?.[0];

  return (
    <div className="space-y-6">
      <PageHeader title="Email templates" description="The wording of the emails ProcuraFlow sends on your behalf." />
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
                  "flex w-full items-center justify-between rounded-control px-3 py-2 text-left text-sm font-medium",
                  template.key === selected.key
                    ? "bg-brand-subtle text-brand-subtle-fg"
                    : "text-text-secondary hover:bg-bg hover:text-text-primary",
                )}
              >
                {template.label}
                {template.is_customised && <span className="text-xs font-normal text-text-muted">customised</span>}
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
