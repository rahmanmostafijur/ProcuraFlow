import { z } from "zod";

type LineProduct = { product_id: string };

export function duplicateProductMessage(productId: string): string {
  return `Each product can appear only once per purchase order (product ${productId} is repeated). Combine the quantities into one line.`;
}

// Products picked on the other lines, so each line's picker can rule them out.
export function productIdsChosenOnOtherLines(items: readonly LineProduct[], index: number): Set<string> {
  return new Set(items.filter((item, i) => i !== index && item.product_id !== "").map((item) => item.product_id));
}

const itemSchema = z.object({
  product_id: z.string().min(1, "Select a product"),
  quantity: z.coerce.number().int().positive("Must be greater than 0"),
  unit_price: z.coerce.number().min(0, "Must be zero or more"),
});

// Mirrors the API, which rejects a purchase order that lists a product on more than one line.
const itemsSchema = z
  .array(itemSchema)
  .min(1, "Add at least one line item")
  .superRefine((items, ctx) => {
    const seen = new Set<string>();
    items.forEach((item, index) => {
      if (item.product_id !== "" && seen.has(item.product_id)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: [index, "product_id"],
          message: duplicateProductMessage(item.product_id),
        });
      }
      seen.add(item.product_id);
    });
  });

export const purchaseOrderFormSchema = z.object({
  supplier_id: z.string().min(1, "Select a supplier"),
  expected_delivery_date: z.string().optional(),
  notes: z.string().optional(),
  items: itemsSchema,
});

export type PurchaseOrderFormValues = z.infer<typeof purchaseOrderFormSchema>;
