import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useProducts } from "@/api/products";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";

const schema = z.object({
  product_id: z.string().min(1, "Select a product"),
  quantity_delta: z.coerce.number().int().refine((val) => val !== 0, "Enter a non-zero quantity"),
  reason: z.string().min(1, "Reason is required").max(255),
});

type FormValues = z.infer<typeof schema>;

interface InventoryAdjustmentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (values: { product_id: number; quantity_delta: number; reason: string }) => Promise<void>;
  isSubmitting: boolean;
}

export function InventoryAdjustmentModal({
  isOpen,
  onClose,
  onSubmit,
  isSubmitting,
}: InventoryAdjustmentModalProps) {
  const { data: products } = useProducts({ page: 1, page_size: 100, is_active: true });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const submit = handleSubmit(async (values) => {
    await onSubmit({
      product_id: Number(values.product_id),
      quantity_delta: values.quantity_delta,
      reason: values.reason,
    });
    reset();
  });

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Adjust Stock" size="sm">
      <form onSubmit={submit} className="space-y-4">
        <div>
          <Label htmlFor="product_id" required>
            Product
          </Label>
          <Select id="product_id" error={errors.product_id?.message} {...register("product_id")}>
            <option value="">Select a product</option>
            {products?.items.map((product) => (
              <option key={product.id} value={product.id}>
                {product.sku} &mdash; {product.name} (stock: {product.current_stock})
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor="quantity_delta" required>
            Quantity change
          </Label>
          <Input
            id="quantity_delta"
            type="number"
            placeholder="e.g. 10 or -5"
            error={errors.quantity_delta?.message}
            {...register("quantity_delta")}
          />
          <p className="mt-1 text-xs text-slate-500">Use a positive number to add stock, negative to remove.</p>
        </div>
        <div>
          <Label htmlFor="reason" required>
            Reason
          </Label>
          <Input id="reason" error={errors.reason?.message} {...register("reason")} />
        </div>
        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Saving…" : "Apply Adjustment"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
