import { z } from "zod";

import type { ProductInput } from "@/api/products";

export const productFormSchema = z.object({
  sku: z.string().min(1, "SKU is required").max(64),
  name: z.string().min(1, "Name is required").max(255),
  category_id: z.string().optional(),
  unit: z.string().min(1, "Unit is required").max(32),
  cost: z.coerce.number().min(0, "Cost must be zero or more"),
  minimum_stock: z.coerce.number().int().min(0, "Minimum stock must be zero or more"),
  supplier_id: z.string().optional(),
  is_active: z.enum(["true", "false"]).optional(),
});

export type ProductFormValues = z.infer<typeof productFormSchema>;

export type ProductPayload = ProductInput & { is_active?: boolean };

// The create endpoint rejects unknown fields, so the active flag is only sent when editing.
export function toProductPayload(values: ProductFormValues, isEditing: boolean): ProductPayload {
  const payload: ProductInput = {
    sku: values.sku,
    name: values.name,
    category_id: values.category_id ? Number(values.category_id) : null,
    unit: values.unit,
    cost: values.cost.toFixed(2),
    minimum_stock: values.minimum_stock,
    supplier_id: values.supplier_id ? Number(values.supplier_id) : null,
  };
  if (!isEditing || !values.is_active) {
    return payload;
  }
  return { ...payload, is_active: values.is_active === "true" };
}
