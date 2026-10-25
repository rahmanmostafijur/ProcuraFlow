import { z } from "zod";

import type { PurchaseRequestInput } from "@/api/purchaseRequests";
import type { PurchaseRequest } from "@/api/types";

const PRICE_PATTERN = /^\d{1,10}(\.\d{1,4})?$/;

const lineSchema = z.object({
  description: z.string().trim().min(1, "Describe what is needed").max(500, "At most 500 characters"),
  quantity: z.coerce
    .number({ invalid_type_error: "Enter a quantity" })
    .int("Whole units only")
    .positive("Must be greater than 0")
    .max(1_000_000),
  unit: z.string().trim().min(1, "Enter a unit").max(32, "At most 32 characters"),
  estimated_unit_price: z.string().trim().regex(PRICE_PATTERN, "A price with up to 4 decimals"),
  // Set when a catalog item was picked; these travel with the line but are never typed.
  catalog_item_id: z.string(),
  product_id: z.string(),
  supplier_id: z.string(),
});

export const requestFormSchema = z.object({
  title: z.string().trim().min(1, "Give the request a title").max(200, "At most 200 characters"),
  notes: z.string().max(5000, "At most 5000 characters"),
  cost_centre_id: z.string(),
  currency_code: z.string(),
  needed_by: z.string(),
  lines: z.array(lineSchema).min(1, "Add at least one line").max(100),
});

export type RequestFormValues = z.infer<typeof requestFormSchema>;
export type RequestLineValues = RequestFormValues["lines"][number];

export const EMPTY_LINE: RequestLineValues = {
  description: "",
  quantity: 1,
  unit: "unit",
  estimated_unit_price: "",
  catalog_item_id: "",
  product_id: "",
  supplier_id: "",
};

export const EMPTY_REQUEST: RequestFormValues = {
  title: "",
  notes: "",
  cost_centre_id: "",
  currency_code: "",
  needed_by: "",
  lines: [EMPTY_LINE],
};

export function valuesFromRequest(request: PurchaseRequest): RequestFormValues {
  return {
    title: request.title,
    notes: request.notes ?? "",
    cost_centre_id: request.cost_centre_id === null ? "" : String(request.cost_centre_id),
    currency_code: request.currency_code,
    needed_by: request.needed_by ?? "",
    lines: request.lines.map((line) => ({
      description: line.description,
      quantity: line.quantity,
      unit: line.unit,
      estimated_unit_price: line.estimated_unit_price,
      catalog_item_id: line.catalog_item_id === null ? "" : String(line.catalog_item_id),
      product_id: line.product_id === null ? "" : String(line.product_id),
      supplier_id: line.supplier_id === null ? "" : String(line.supplier_id),
    })),
  };
}

function idOrNull(value: string): number | null {
  return value === "" ? null : Number(value);
}

export function toRequestInput(values: RequestFormValues): PurchaseRequestInput {
  return {
    title: values.title.trim(),
    notes: values.notes.trim() === "" ? null : values.notes.trim(),
    cost_centre_id: idOrNull(values.cost_centre_id),
    currency_code: values.currency_code === "" ? null : values.currency_code,
    needed_by: values.needed_by === "" ? null : values.needed_by,
    lines: values.lines.map((line) => ({
      description: line.description.trim(),
      quantity: line.quantity,
      unit: line.unit.trim(),
      estimated_unit_price: line.estimated_unit_price.trim(),
      catalog_item_id: idOrNull(line.catalog_item_id),
      product_id: idOrNull(line.product_id),
      supplier_id: idOrNull(line.supplier_id),
    })),
  };
}
