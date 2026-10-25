import { z } from "zod";

import type { CatalogItem } from "@/api/types";

const PRICE_PATTERN = /^\d{1,10}(\.\d{1,4})?$/;

export const catalogFormSchema = z
  .object({
    product_id: z.string().min(1, "Choose a product"),
    supplier_id: z.string().min(1, "Choose a supplier"),
    contract_price: z.string().trim().regex(PRICE_PATTERN, "A price with up to 4 decimals"),
    currency_code: z.string(),
    lead_time_days: z.coerce
      .number({ invalid_type_error: "Enter a number of days" })
      .int("Whole days only")
      .min(0, "Zero or more")
      .max(3650, "At most 3650"),
    valid_from: z.string(),
    valid_until: z.string(),
    is_active: z.boolean(),
  })
  .refine(
    (values) => values.valid_from === "" || values.valid_until === "" || values.valid_until >= values.valid_from,
    {
      path: ["valid_until"],
      message: "The contract cannot end before it starts",
    },
  );

export type CatalogFormValues = z.infer<typeof catalogFormSchema>;

export const EMPTY_CATALOG_ITEM: CatalogFormValues = {
  product_id: "",
  supplier_id: "",
  contract_price: "",
  currency_code: "",
  lead_time_days: 0,
  valid_from: "",
  valid_until: "",
  is_active: true,
};

export function valuesFromItem(item: CatalogItem): CatalogFormValues {
  return {
    product_id: String(item.product_id),
    supplier_id: String(item.supplier_id),
    contract_price: item.contract_price,
    currency_code: item.currency_code,
    lead_time_days: item.lead_time_days,
    valid_from: item.valid_from ?? "",
    valid_until: item.valid_until ?? "",
    is_active: item.is_active,
  };
}
