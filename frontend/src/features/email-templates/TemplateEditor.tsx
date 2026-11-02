import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { extractErrorMessage } from "@/api/client";
import { type EmailTemplate, useResetEmailTemplate, useSaveEmailTemplate } from "@/api/emailTemplates";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Textarea } from "@/components/ui/Textarea";
import { useToast } from "@/components/ui/toast-context";
import { useUnsavedChangesWarning } from "@/lib/use-unsaved-changes";

const schema = z.object({
  subject: z.string().min(1, "Subject is required"),
  body: z.string().min(1, "Body is required"),
});

type FormValues = z.infer<typeof schema>;

export function TemplateEditor({ template }: { template: EmailTemplate }) {
  const { showToast } = useToast();
  const saveTemplate = useSaveEmailTemplate();
  const resetTemplate = useResetEmailTemplate();
  const [serverError, setServerError] = useState<string | null>(null);
  const [isResetOpen, setResetOpen] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isDirty },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { subject: template.subject, body: template.body },
  });
  useUnsavedChangesWarning(isDirty);

  const onSubmit = async (values: FormValues) => {
    setServerError(null);
    try {
      const saved = await saveTemplate.mutateAsync({ key: template.key, ...values });
      reset({ subject: saved.subject, body: saved.body });
      showToast("Template saved");
    } catch (error) {
      // A 422 explains which variable or syntax is wrong, so it belongs next to the fields.
      setServerError(extractErrorMessage(error));
    }
  };

  const onReset = async () => {
    try {
      const restored = await resetTemplate.mutateAsync(template.key);
      reset({ subject: restored.subject, body: restored.body });
      setServerError(null);
      showToast("Template reset to default");
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    } finally {
      setResetOpen(false);
    }
  };

  return (
    <Card className="p-6">
      <div className="mb-4 flex items-center gap-3">
        <h2 className="text-base font-semibold text-text-primary">{template.label}</h2>
        {template.is_customised && <Badge status="active">Customised</Badge>}
      </div>

      <div className="mb-4">
        <p className="mb-1 text-sm font-medium text-text-secondary">Available variables</p>
        <ul className="flex flex-wrap gap-2">
          {template.variables.map((name) => (
            <li key={name}>
              <code className="rounded bg-bg px-2 py-0.5 text-xs text-text-secondary">{`{{ ${name} }}`}</code>
            </li>
          ))}
        </ul>
      </div>

      <form onSubmit={(event) => void handleSubmit(onSubmit)(event)} className="space-y-4">
        {serverError && (
          <div role="alert" className="rounded-control bg-danger-bg px-3 py-2 text-sm text-danger-fg">
            {serverError}
          </div>
        )}
        <div>
          <Label htmlFor="template_subject" required>
            Subject
          </Label>
          <Input id="template_subject" error={errors.subject?.message} {...register("subject")} />
        </div>
        <div>
          <Label htmlFor="template_body" required>
            Body
          </Label>
          <Textarea id="template_body" rows={10} error={errors.body?.message} {...register("body")} />
        </div>
        <div className="flex justify-between gap-2">
          <Button
            type="button"
            variant="secondary"
            disabled={!template.is_customised}
            onClick={() => setResetOpen(true)}
          >
            Reset to default
          </Button>
          <Button type="submit" disabled={!isDirty || saveTemplate.isPending}>
            {saveTemplate.isPending ? "Saving…" : "Save template"}
          </Button>
        </div>
      </form>

      <ConfirmDialog
        isOpen={isResetOpen}
        title="Reset to default"
        message="This discards your changes to this template and restores the built-in wording."
        confirmLabel="Reset"
        variant="danger"
        isLoading={resetTemplate.isPending}
        onConfirm={() => void onReset()}
        onCancel={() => setResetOpen(false)}
      />
    </Card>
  );
}
