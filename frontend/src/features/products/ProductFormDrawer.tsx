import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useCategories } from "@/api/categories";
import type { ProductInput } from "@/api/products";
import { useSuppliers } from "@/api/suppliers";
import type { Product } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Drawer } from "@/components/ui/Drawer";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Select } from "@/components/ui/Select";

const schema = z.object({
  sku: z.string().min(1, "SKU is required").max(64),
  name: z.string().min(1, "Name is required").max(255),
  category_id: z.string().optional(),
  unit: z.string().min(1, "Unit is required").max(32),
  cost: z.coerce.number().min(0, "Cost must be zero or more"),
  minimum_stock: z.coerce.number().int().min(0, "Minimum stock must be zero or more"),
  supplier_id: z.string().optional(),
  current_stock: z.coerce.number().int().min(0).optional(),
  is_active: z.enum(["true", "false"]).optional(),
});

type FormValues = z.infer<typeof schema>;

interface ProductFormDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  product: Product | null;
  onSubmit: (values: ProductInput & { is_active?: boolean }) => Promise<void>;
  isSubmitting: boolean;
}

export function ProductFormDrawer({ isOpen, onClose, product, onSubmit, isSubmitting }: ProductFormDrawerProps) {
  const { data: categories } = useCategories();
  const { data: suppliers } = useSuppliers({ page: 1, page_size: 100, is_active: true });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (isOpen) {
      reset({
        sku: product?.sku ?? "",
        name: product?.name ?? "",
        category_id: product?.category_id ? String(product.category_id) : "",
        unit: product?.unit ?? "unit",
        cost: product ? Number(product.cost) : 0,
        minimum_stock: product?.minimum_stock ?? 0,
        supplier_id: product?.supplier_id ? String(product.supplier_id) : "",
        current_stock: product?.current_stock ?? 0,
        is_active: product ? (product.is_active ? "true" : "false") : "true",
      });
    }
  }, [isOpen, product, reset]);

  const submit = handleSubmit(async (values) => {
    await onSubmit({
      sku: values.sku,
      name: values.name,
      category_id: values.category_id ? Number(values.category_id) : null,
      unit: values.unit,
      cost: values.cost.toFixed(2),
      minimum_stock: values.minimum_stock,
      supplier_id: values.supplier_id ? Number(values.supplier_id) : null,
      current_stock: product ? undefined : values.current_stock,
      is_active: values.is_active ? values.is_active === "true" : undefined,
    });
  });

  return (
    <Drawer isOpen={isOpen} onClose={onClose} title={product ? "Edit Product" : "New Product"}>
      <form onSubmit={submit} className="space-y-4">
        <div>
          <Label htmlFor="sku" required>
            SKU
          </Label>
          <Input id="sku" disabled={Boolean(product)} error={errors.sku?.message} {...register("sku")} />
        </div>
        <div>
          <Label htmlFor="name" required>
            Name
          </Label>
          <Input id="name" error={errors.name?.message} {...register("name")} />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label htmlFor="category_id">Category</Label>
            <Select id="category_id" {...register("category_id")}>
              <option value="">Uncategorized</option>
              {categories?.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="supplier_id">Supplier</Label>
            <Select id="supplier_id" {...register("supplier_id")}>
              <option value="">None</option>
              {suppliers?.items.map((supplier) => (
                <option key={supplier.id} value={supplier.id}>
                  {supplier.name}
                </option>
              ))}
            </Select>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <Label htmlFor="unit" required>
              Unit
            </Label>
            <Input id="unit" error={errors.unit?.message} {...register("unit")} />
          </div>
          <div>
            <Label htmlFor="cost" required>
              Cost
            </Label>
            <Input id="cost" type="number" step="0.01" error={errors.cost?.message} {...register("cost")} />
          </div>
          <div>
            <Label htmlFor="minimum_stock" required>
              Min. Stock
            </Label>
            <Input
              id="minimum_stock"
              type="number"
              error={errors.minimum_stock?.message}
              {...register("minimum_stock")}
            />
          </div>
        </div>
        {!product && (
          <div>
            <Label htmlFor="current_stock">Initial Stock</Label>
            <Input id="current_stock" type="number" {...register("current_stock")} />
          </div>
        )}
        {product && (
          <div>
            <Label htmlFor="is_active">Status</Label>
            <Select id="is_active" {...register("is_active")}>
              <option value="true">Active</option>
              <option value="false">Inactive</option>
            </Select>
          </div>
        )}
        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Saving…" : "Save"}
          </Button>
        </div>
      </form>
    </Drawer>
  );
}
