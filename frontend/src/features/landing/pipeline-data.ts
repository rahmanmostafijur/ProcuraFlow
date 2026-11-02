import type { LifecycleStep, StepState } from "@/components/ui/LifecycleStepper";

/** Sample order for the hero animation: two lines, each rounded half-up once, and the total is their sum. */
export const SAMPLE_LINES = [
  { description: "Laptop stand, 12 x 41.50", net: "498.00", tax: "99.60" },
  { description: "USB-C cable, 3 x 19.99", net: "59.97", tax: "11.99" },
] as const;

export const SAMPLE_TOTALS = { net: "557.97", tax: "111.59", gross: "669.56", currency: "EUR", locale: "en-IE" };

export interface PipelineStage {
  id: string;
  label: string;
  /** Document shown while this stage is current. */
  documentNumber: string;
  documentType: string;
  status: string;
  note: string;
  committed: number;
  paid: number;
}

export const PIPELINE_STAGES: PipelineStage[] = [
  {
    id: "request",
    label: "Request",
    documentNumber: "PR-2026-00042",
    documentType: "Purchase request",
    status: "submitted",
    note: "Raised by Facilities, waiting for a decision.",
    committed: 0,
    paid: 0,
  },
  {
    id: "approve",
    label: "Approve",
    documentNumber: "PR-2026-00042",
    documentType: "Purchase request",
    status: "approved",
    note: "Approved by the budget owner within the cost centre limit.",
    committed: 0,
    paid: 0,
  },
  {
    id: "order",
    label: "Order",
    documentNumber: "PO-2026-00018",
    documentType: "Purchase order",
    status: "ordered",
    note: "Sent to the supplier. The amount is now committed against the budget.",
    committed: 669.56,
    paid: 0,
  },
  {
    id: "receive",
    label: "Receive",
    documentNumber: "PO-2026-00018",
    documentType: "Purchase order",
    status: "received",
    note: "Both lines booked into stock at the warehouse.",
    committed: 669.56,
    paid: 0,
  },
  {
    id: "match",
    label: "Match",
    documentNumber: "INV-88214",
    documentType: "Supplier invoice",
    status: "matched",
    note: "Invoice total equals order and receipt, line by line.",
    committed: 669.56,
    paid: 0,
  },
  {
    id: "pay",
    label: "Pay",
    documentNumber: "INV-88214",
    documentType: "Supplier invoice",
    status: "paid",
    note: "Released in a payment run. Committed spend becomes paid spend.",
    committed: 0,
    paid: 669.56,
  },
];

/** Steps before `current` are done, `current` is current, the rest are upcoming; the last stage counts as done. */
export function stepsFor(current: number): LifecycleStep[] {
  return PIPELINE_STAGES.map((stage, index) => {
    const isFinal = current === PIPELINE_STAGES.length - 1;
    let state: StepState = "upcoming";
    if (index < current || (isFinal && index === current)) state = "done";
    else if (index === current) state = "current";
    return { id: stage.id, label: stage.label, state };
  });
}
