import { zodResolver } from "@hookform/resolvers/zod";
import { Plus, Trash2 } from "lucide-react";
import { useEffect } from "react";
import { useFieldArray, useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { useTaxRates } from "@/api/finance";
import { useProducts } from "@/api/products";
import type { AmendInput } from "@/api/purchaseOrders";
import type { PurchaseOrder } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";

import { productIdsChosenOnOtherLines, purchaseOrderItemsSchema } from "./lineItems";

const amendSchema = z.object({
  reason: z.string().trim().min(1, "Say why the order is changing").max(500, "At most 500 characters"),
  expected_delivery_date: z.string(),
  notes: z.string().max(5000, "At most 5000 characters"),
  items: purchaseOrderItemsSchema,
});

type AmendValues = z.infer<typeof amendSchema>;

interface AmendPurchaseOrderModalProps {
  isOpen: boolean;
  po: PurchaseOrder;
  isSubmitting: boolean;
  onClose: () => void;
  onSubmit: (input: AmendInput) => Promise<void>;
}

function valuesFromOrder(po: PurchaseOrder): AmendValues {
  return {
    reason: "",
    expected_delivery_date: po.expected_delivery_date ?? "",
    notes: po.notes ?? "",
    items: po.items.map((item) => ({
      product_id: String(item.product_id),
      quantity: item.quantity,
      unit_price: Number(item.unit_price),
      tax_rate_id: item.tax_rate_id === null ? "" : String(item.tax_rate_id),
    })),
  };
}

export function AmendPurchaseOrderModal({ isOpen, po, isSubmitting, onClose, onSubmit }: AmendPurchaseOrderModalProps) {
  const { data: products } = useProducts({ page: 1, page_size: 100, is_active: true });
  const { data: taxRates } = useTaxRates(true);
  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AmendValues>({ resolver: zodResolver(amendSchema), defaultValues: valuesFromOrder(po) });
  const { fields, append, remove } = useFieldArray({ control, name: "items" });
  const lineItems = useWatch({ control, name: "items" }) ?? [];

  useEffect(() => {
    if (isOpen) reset(valuesFromOrder(po));
  }, [isOpen, po, reset]);

  const submit = handleSubmit(async (values) => {
    await onSubmit({
      reason: values.reason.trim(),
      expected_delivery_date: values.expected_delivery_date === "" ? null : values.expected_delivery_date,
      notes: values.notes.trim() === "" ? null : values.notes.trim(),
      items: values.items.map((item) => ({
        product_id: Number(item.product_id),
        quantity: item.quantity,
        unit_price: item.unit_price.toFixed(4),
        tax_rate_id: item.tax_rate_id ? Number(item.tax_rate_id) : null,
      })),
    });
  });

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Amend ${po.po_number}`} size="lg">
      <form onSubmit={(event) => void submit(event)} noValidate className="space-y-4">
        <p className="rounded-md bg-slate-50 p-3 text-sm text-slate-600">
          A change that keeps or lowers the total takes effect straight away. A change that raises the total waits for
          approval, and the order stays as it is until then.
        </p>
        <div>
          <Label htmlFor="amend_reason" required>
            Reason for the change
          </Label>
          <Textarea id="amend_reason" rows={2} error={errors.reason?.message} {...register("reason")} />
        </div>
        <div className="max-w-xs">
          <Label htmlFor="amend_expected">Expected delivery</Label>
          <Input id="amend_expected" type="date" {...register("expected_delivery_date")} />
        </div>
        <div>
          <Label htmlFor="amend_notes">Notes</Label>
          <Textarea id="amend_notes" rows={2} error={errors.notes?.message} {...register("notes")} />
        </div>

        <fieldset>
          <legend className="mb-2 text-sm font-medium text-slate-700">Line items</legend>
          {errors.items?.message && <p className="mb-2 text-xs text-red-600">{errors.items.message}</p>}
          <div className="space-y-2">
            {fields.map((field, index) => {
              const n = index + 1;
              const taken = productIdsChosenOnOtherLines(lineItems, index);
              const lineErrors = errors.items?.[index];
              return (
                <div key={field.id} className="flex items-start gap-2">
                  <div className="flex-1">
                    <Select
                      aria-label={`Product for line ${n}`}
                      error={lineErrors?.product_id?.message}
                      {...register(`items.${index}.product_id` as const)}
                    >
                      <option value="">Select a product</option>
                      {products?.items.map((product) => (
                        <option key={product.id} value={product.id} disabled={taken.has(String(product.id))}>
                          {product.sku} — {product.name}
                        </option>
                      ))}
                      {po.items
                        .filter((item) => !products?.items.some((product) => product.id === item.product_id))
                        .map((item) => (
                          <option key={item.product_id} value={item.product_id}>
                            Product {item.product_id}
                          </option>
                        ))}
                    </Select>
                  </div>
                  <div className="w-24">
                    <Input
                      type="number"
                      aria-label={`Quantity for line ${n}`}
                      error={lineErrors?.quantity?.message}
                      {...register(`items.${index}.quantity` as const)}
                    />
                  </div>
                  <div className="w-28">
                    <Input
                      type="number"
                      step="0.0001"
                      aria-label={`Unit price for line ${n}`}
                      error={lineErrors?.unit_price?.message}
                      {...register(`items.${index}.unit_price` as const)}
                    />
                  </div>
                  <div className="w-40">
                    <Select aria-label={`Tax rate for line ${n}`} {...register(`items.${index}.tax_rate_id` as const)}>
                      <option value="">No tax</option>
                      {taxRates?.map((rate) => (
                        <option key={rate.id} value={rate.id}>
                          {rate.name}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    aria-label={`Remove line ${n}`}
                    disabled={fields.length === 1}
                    onClick={() => remove(index)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              );
            })}
          </div>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="mt-2"
            onClick={() => append({ product_id: "", quantity: 1, unit_price: 0, tax_rate_id: "" })}
          >
            <Plus className="h-3.5 w-3.5" /> Add item
          </Button>
        </fieldset>

        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Saving…" : "Submit change"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
