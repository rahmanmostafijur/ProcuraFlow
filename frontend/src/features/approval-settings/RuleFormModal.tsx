import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";

import { extractErrorMessage } from "@/api/client";
import { useSaveRule, type ApprovalRuleInput } from "@/api/approvals";
import { useRoles } from "@/api/roles";
import type { ApprovalRule } from "@/api/types";
import { DOCUMENT_TYPE_LABELS } from "@/components/approvals/documentLinks";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";
import { useToast } from "@/components/ui/toast-context";

import { EMPTY_RULE, MAX_STEPS, ruleFormSchema, toRuleInput, valuesFromRule, type RuleFormValues } from "./ruleForm";

interface RuleFormModalProps {
  isOpen: boolean;
  rule: ApprovalRule | null;
  onClose: () => void;
}

export function RuleFormModal({ isOpen, rule, onClose }: RuleFormModalProps) {
  const { showToast } = useToast();
  const { data: roles } = useRoles();
  const saveRule = useSaveRule();
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<RuleFormValues>({ resolver: zodResolver(ruleFormSchema), defaultValues: EMPTY_RULE });
  const { fields, append, remove, move } = useFieldArray({ control, name: "steps" });

  useEffect(() => {
    if (isOpen) reset(rule ? valuesFromRule(rule) : EMPTY_RULE);
  }, [isOpen, rule, reset]);

  const close = () => {
    setServerError(null);
    onClose();
  };

  const submit = handleSubmit(async (values) => {
    const input: ApprovalRuleInput = toRuleInput(values);
    setServerError(null);
    try {
      if (rule) {
        await saveRule.mutateAsync({
          id: rule.id,
          name: input.name,
          min_amount: input.min_amount,
          max_amount: input.max_amount,
          is_active: input.is_active,
          steps: input.steps,
        });
      } else {
        await saveRule.mutateAsync(input);
      }
      showToast(rule ? "Rule updated" : "Rule created");
      close();
    } catch (error) {
      // The API explains an overlapping amount band in words; show it next to the form, not only in a toast.
      setServerError(extractErrorMessage(error));
    }
  });

  return (
    <Modal isOpen={isOpen} onClose={close} title={rule ? "Edit rule" : "New rule"} size="lg">
      <form onSubmit={(event) => void submit(event)} noValidate className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="rule_name" required>
              Rule name
            </Label>
            <Input id="rule_name" error={errors.name?.message} {...register("name")} />
          </div>
          <div>
            <Label htmlFor="rule_document_type">Applies to</Label>
            <Select id="rule_document_type" disabled={rule !== null} {...register("document_type")}>
              {Object.entries(DOCUMENT_TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="rule_min">From amount</Label>
            <Input id="rule_min" inputMode="decimal" error={errors.min_amount?.message} {...register("min_amount")} />
          </div>
          <div>
            <Label htmlFor="rule_max">Up to amount (blank for no limit)</Label>
            <Input id="rule_max" inputMode="decimal" error={errors.max_amount?.message} {...register("max_amount")} />
          </div>
          <label className="flex items-center gap-2 text-sm text-text-secondary">
            <input type="checkbox" {...register("is_active")} /> Rule is active
          </label>
        </div>

        <fieldset>
          <legend className="mb-1 text-sm font-medium text-text-secondary">Approval steps, in order</legend>
          <p className="mb-2 text-xs text-text-secondary">
            Each step must be approved by someone with the chosen role. Amounts are in the company currency.
          </p>
          {errors.steps?.message && <p className="mb-2 text-xs text-danger-fg">{errors.steps.message}</p>}
          <ol className="space-y-2">
            {fields.map((field, index) => {
              const n = index + 1;
              return (
                <li key={field.id} className="flex items-start gap-2">
                  <span className="w-12 pt-2 text-sm text-text-secondary">Step {n}</span>
                  <Select
                    aria-label={`Role for step ${n}`}
                    error={errors.steps?.[index]?.approver_role_id?.message}
                    {...register(`steps.${index}.approver_role_id` as const)}
                  >
                    <option value="">Choose a role</option>
                    {roles?.map((role) => (
                      <option key={role.id} value={role.id}>
                        {role.name.replace(/_/g, " ")}
                      </option>
                    ))}
                  </Select>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    aria-label={`Move step ${n} up`}
                    disabled={index === 0}
                    onClick={() => move(index, index - 1)}
                  >
                    <ArrowUp className="h-4 w-4" />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    aria-label={`Move step ${n} down`}
                    disabled={index === fields.length - 1}
                    onClick={() => move(index, index + 1)}
                  >
                    <ArrowDown className="h-4 w-4" />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    aria-label={`Remove step ${n}`}
                    disabled={fields.length === 1}
                    onClick={() => remove(index)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </li>
              );
            })}
          </ol>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="mt-2"
            disabled={fields.length >= MAX_STEPS}
            onClick={() => append({ approver_role_id: "" })}
          >
            <Plus className="h-3.5 w-3.5" /> Add step
          </Button>
        </fieldset>

        {serverError && (
          <p role="alert" className="rounded-control border border-border bg-danger-bg p-3 text-sm text-danger-fg">
            {serverError}
          </p>
        )}
        <div className="flex justify-end gap-3">
          <Button type="button" variant="secondary" onClick={close}>
            Cancel
          </Button>
          <Button type="submit" disabled={saveRule.isPending}>
            {saveRule.isPending ? "Saving…" : "Save rule"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
