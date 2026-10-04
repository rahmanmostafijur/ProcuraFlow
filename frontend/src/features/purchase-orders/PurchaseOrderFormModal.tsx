import { zodResolver } from "@hookform/resolvers/zod";
import { Plus, Trash2 } from "lucide-react";
import { useEffect } from "react";
import { useFieldArray, useForm, useWatch } from "react-hook-form";

import type { PurchaseOrderInput } from "@/api/purchaseOrders";
import { useProducts } from "@/api/products";
import { useSuppliers } from "@/api/suppliers";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";

import { productIdsChosenOnOtherLines, purchaseOrderFormSchema, type PurchaseOrderFormValues } from "./lineItems";

interface PurchaseOrderFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (values: PurchaseOrderInput) => Promise<void>;
  isSubmitting: boolean;
}

export function PurchaseOrderFormModal({ isOpen, onClose, onSubmit, isSubmitting }: PurchaseOrderFormModalProps) {
  const { data: suppliers } = useSuppliers({ page: 1, page_size: 100, is_active: true });
  const { data: products } = useProducts({ page: 1, page_size: 100, is_active: true });

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<PurchaseOrderFormValues>({
    resolver: zodResolver(purchaseOrderFormSchema),
    defaultValues: { items: [{ product_id: "", quantity: 1, unit_price: 0 }] },
  });

  const { fields, append, remove } = useFieldArray({ control, name: "items" });
  const lineItems = useWatch({ control, name: "items" }) ?? [];

  useEffect(() => {
    if (isOpen) {
      reset({
        supplier_id: "",
        expected_delivery_date: "",
        notes: "",
        items: [{ product_id: "", quantity: 1, unit_price: 0 }],
      });
    }
  }, [isOpen, reset]);

  const submit = handleSubmit(async (values) => {
    await onSubmit({
      supplier_id: Number(values.supplier_id),
      expected_delivery_date: values.expected_delivery_date || null,
      notes: values.notes || null,
      items: values.items.map((item) => ({
        product_id: Number(item.product_id),
        quantity: item.quantity,
        unit_price: item.unit_price.toFixed(2),
      })),
    });
  });

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="New Purchase Order" size="lg">
      <form onSubmit={submit} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label htmlFor="supplier_id" required>
              Supplier
            </Label>
            <Select id="supplier_id" error={errors.supplier_id?.message} {...register("supplier_id")}>
              <option value="">Select a supplier</option>
              {suppliers?.items.map((supplier) => (
                <option key={supplier.id} value={supplier.id}>
                  {supplier.name}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="expected_delivery_date">Expected Delivery</Label>
            <Input id="expected_delivery_date" type="date" {...register("expected_delivery_date")} />
          </div>
        </div>

        <div>
          <Label htmlFor="notes">Notes</Label>
          <Textarea id="notes" rows={2} {...register("notes")} />
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between">
            <Label>Line Items</Label>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => append({ product_id: "", quantity: 1, unit_price: 0 })}
            >
              <Plus className="h-3.5 w-3.5" /> Add item
            </Button>
          </div>
          {errors.items?.message && <p className="mb-2 text-xs text-red-600">{errors.items.message}</p>}
          <div className="space-y-2">
            {fields.map((field, index) => {
              const takenProductIds = productIdsChosenOnOtherLines(lineItems, index);
              return (
                <div key={field.id} className="flex items-start gap-2">
                  <div className="flex-1">
                    <Select
                      error={errors.items?.[index]?.product_id?.message}
                      {...register(`items.${index}.product_id` as const)}
                    >
                      <option value="">Select a product</option>
                      {products?.items.map((product) => (
                        <option key={product.id} value={product.id} disabled={takenProductIds.has(String(product.id))}>
                          {product.sku} &mdash; {product.name}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <div className="w-24">
                    <Input type="number" placeholder="Qty" {...register(`items.${index}.quantity` as const)} />
                  </div>
                  <div className="w-28">
                    <Input
                      type="number"
                      step="0.01"
                      placeholder="Unit price"
                      {...register(`items.${index}.unit_price` as const)}
                    />
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => remove(index)}
                    disabled={fields.length === 1}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              );
            })}
          </div>
        </div>

        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Creating…" : "Create Purchase Order"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
