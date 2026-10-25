import { z } from "zod";

import type { ApprovalRuleInput } from "@/api/approvals";
import type { ApprovalRule } from "@/api/types";

export const MAX_STEPS = 5;
const AMOUNT_PATTERN = /^\d{1,14}(\.\d{1,4})?$/;

export const ruleFormSchema = z
  .object({
    name: z.string().trim().min(1, "Name the rule").max(150, "At most 150 characters"),
    document_type: z.enum(["purchase_request", "purchase_order", "purchase_order_amendment", "invoice_exception"]),
    min_amount: z.string().trim().regex(AMOUNT_PATTERN, "An amount with up to 4 decimals"),
    max_amount: z
      .string()
      .trim()
      .refine((value) => value === "" || AMOUNT_PATTERN.test(value), "An amount with up to 4 decimals"),
    is_active: z.boolean(),
    steps: z
      .array(z.object({ approver_role_id: z.string().min(1, "Choose a role") }))
      .min(1, "Add at least one step")
      .max(MAX_STEPS, `At most ${MAX_STEPS} steps`),
  })
  .refine(
    (values) =>
      values.max_amount === "" ||
      !AMOUNT_PATTERN.test(values.min_amount) ||
      Number(values.max_amount) > Number(values.min_amount),
    {
      path: ["max_amount"],
      message: "The upper limit must be greater than the lower limit",
    },
  );

export type RuleFormValues = z.infer<typeof ruleFormSchema>;

export const EMPTY_RULE: RuleFormValues = {
  name: "",
  document_type: "purchase_request",
  min_amount: "0",
  max_amount: "",
  is_active: true,
  steps: [{ approver_role_id: "" }],
};

export function valuesFromRule(rule: ApprovalRule): RuleFormValues {
  return {
    name: rule.name,
    document_type: rule.document_type,
    min_amount: rule.min_amount,
    max_amount: rule.max_amount ?? "",
    is_active: rule.is_active,
    steps: [...rule.steps]
      .sort((a, b) => a.step_order - b.step_order)
      .map((step) => ({ approver_role_id: String(step.approver_role_id) })),
  };
}

/** The steps keep the order they have on screen; the API numbers them. */
export function toRuleInput(values: RuleFormValues): ApprovalRuleInput {
  return {
    name: values.name.trim(),
    document_type: values.document_type,
    min_amount: values.min_amount.trim(),
    max_amount: values.max_amount.trim() === "" ? null : values.max_amount.trim(),
    is_active: values.is_active,
    steps: values.steps.map((step) => ({ approver_role_id: Number(step.approver_role_id) })),
  };
}
