import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";

import { useCategories } from "@/api/categories";
import { useSuppliers } from "@/api/suppliers";
import type { Product } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Drawer } from "@/components/ui/Drawer";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Select } from "@/components/ui/Select";

import { type ProductFormValues, type ProductPayload, productFormSchema, toProductPayload } from "./productPayload";

interface ProductFormDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  product: Product | null;
  onSubmit: (values: ProductPayload) => Promise<void>;
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
  } = useForm<ProductFormValues>({ resolver: zodResolver(productFormSchema) });

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
        is_active: product ? (product.is_active ? "true" : "false") : "true",
      });
    }
  }, [isOpen, product, reset]);

  const submit = handleSubmit(async (values) => {
    await onSubmit(toProductPayload(values, Boolean(product)));
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
