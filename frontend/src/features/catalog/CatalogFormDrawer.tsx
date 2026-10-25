import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";

import { useSaveCatalogItem } from "@/api/catalog";
import { extractErrorMessage } from "@/api/client";
import { useCurrencies } from "@/api/finance";
import { useProducts } from "@/api/products";
import { useSuppliers } from "@/api/suppliers";
import type { CatalogItem } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Drawer } from "@/components/ui/Drawer";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Select } from "@/components/ui/Select";
import { useToast } from "@/components/ui/toast-context";

import { EMPTY_CATALOG_ITEM, catalogFormSchema, valuesFromItem, type CatalogFormValues } from "./catalogForm";

interface CatalogFormDrawerProps {
  isOpen: boolean;
  item: CatalogItem | null;
  onClose: () => void;
}

export function CatalogFormDrawer({ isOpen, item, onClose }: CatalogFormDrawerProps) {
  const { showToast } = useToast();
  const { data: products } = useProducts({ page: 1, page_size: 100, is_active: true });
  const { data: suppliers } = useSuppliers({ page: 1, page_size: 100, is_active: true });
  const { data: currencies } = useCurrencies(true);
  const save = useSaveCatalogItem();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CatalogFormValues>({ resolver: zodResolver(catalogFormSchema), defaultValues: EMPTY_CATALOG_ITEM });

  useEffect(() => {
    if (isOpen) reset(item ? valuesFromItem(item) : EMPTY_CATALOG_ITEM);
  }, [isOpen, item, reset]);

  const submit = handleSubmit(async (values) => {
    const terms = {
      contract_price: values.contract_price.trim(),
      lead_time_days: values.lead_time_days,
      valid_from: values.valid_from === "" ? null : values.valid_from,
      valid_until: values.valid_until === "" ? null : values.valid_until,
    };
    try {
      if (item) {
        await save.mutateAsync({ id: item.id, ...terms, is_active: values.is_active });
      } else {
        await save.mutateAsync({
          product_id: Number(values.product_id),
          supplier_id: Number(values.supplier_id),
          currency_code: values.currency_code === "" ? null : values.currency_code,
          ...terms,
        });
      }
      showToast(item ? "Catalog item updated" : "Catalog item added");
      onClose();
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  });

  return (
    <Drawer isOpen={isOpen} onClose={onClose} title={item ? "Edit contract price" : "New contract price"}>
      <form onSubmit={(event) => void submit(event)} noValidate className="space-y-4">
        <div>
          <Label htmlFor="catalog_product" required>
            Product
          </Label>
          <Select
            id="catalog_product"
            disabled={item !== null}
            error={errors.product_id?.message}
            {...register("product_id")}
          >
            <option value="">Choose a product</option>
            {products?.items.map((product) => (
              <option key={product.id} value={product.id}>
                {product.sku} — {product.name}
              </option>
            ))}
            {item && !products?.items.some((product) => product.id === item.product_id) && (
              <option value={item.product_id}>{item.product_name}</option>
            )}
          </Select>
        </div>
        <div>
          <Label htmlFor="catalog_supplier" required>
            Supplier
          </Label>
          <Select
            id="catalog_supplier"
            disabled={item !== null}
            error={errors.supplier_id?.message}
            {...register("supplier_id")}
          >
            <option value="">Choose a supplier</option>
            {suppliers?.items.map((supplier) => (
              <option key={supplier.id} value={supplier.id}>
                {supplier.name}
              </option>
            ))}
            {item && !suppliers?.items.some((supplier) => supplier.id === item.supplier_id) && (
              <option value={item.supplier_id}>{item.supplier_name}</option>
            )}
          </Select>
        </div>
        <div>
          <Label htmlFor="catalog_price" required>
            Contract price
          </Label>
          <Input
            id="catalog_price"
            inputMode="decimal"
            error={errors.contract_price?.message}
            {...register("contract_price")}
          />
        </div>
        <div>
          <Label htmlFor="catalog_currency">Price currency</Label>
          <Select id="catalog_currency" disabled={item !== null} {...register("currency_code")}>
            <option value="">Supplier or company default</option>
            {currencies?.map((currency) => (
              <option key={currency.code} value={currency.code}>
                {currency.code} — {currency.name}
              </option>
            ))}
            {item && !currencies?.some((currency) => currency.code === item.currency_code) && (
              <option value={item.currency_code}>{item.currency_code}</option>
            )}
          </Select>
        </div>
        <div>
          <Label htmlFor="catalog_lead_time">Lead time (days)</Label>
          <Input
            id="catalog_lead_time"
            type="number"
            error={errors.lead_time_days?.message}
            {...register("lead_time_days")}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label htmlFor="catalog_valid_from">Valid from</Label>
            <Input id="catalog_valid_from" type="date" {...register("valid_from")} />
          </div>
          <div>
            <Label htmlFor="catalog_valid_until">Valid until</Label>
            <Input
              id="catalog_valid_until"
              type="date"
              error={errors.valid_until?.message}
              {...register("valid_until")}
            />
          </div>
        </div>
        {item && (
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" {...register("is_active")} /> Price is active
          </label>
        )}
        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? "Saving…" : "Save"}
          </Button>
        </div>
      </form>
    </Drawer>
  );
}
