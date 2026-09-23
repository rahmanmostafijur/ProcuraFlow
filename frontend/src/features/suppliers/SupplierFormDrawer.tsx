import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import type { SupplierInput } from "@/api/suppliers";
import type { Supplier } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Drawer } from "@/components/ui/Drawer";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Select } from "@/components/ui/Select";

const schema = z.object({
  name: z.string().min(1, "Name is required").max(255),
  contact_name: z.string().max(255).optional().or(z.literal("")),
  email: z.string().email("Enter a valid email").optional().or(z.literal("")),
  phone: z.string().max(50).optional().or(z.literal("")),
  address: z.string().max(500).optional().or(z.literal("")),
  is_active: z.enum(["true", "false"]).optional(),
});

type FormValues = z.infer<typeof schema>;

interface SupplierFormDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  supplier: Supplier | null;
  onSubmit: (values: SupplierInput & { is_active?: boolean }) => Promise<void>;
  isSubmitting: boolean;
}

export function SupplierFormDrawer({
  isOpen,
  onClose,
  supplier,
  onSubmit,
  isSubmitting,
}: SupplierFormDrawerProps) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (isOpen) {
      reset({
        name: supplier?.name ?? "",
        contact_name: supplier?.contact_name ?? "",
        email: supplier?.email ?? "",
        phone: supplier?.phone ?? "",
        address: supplier?.address ?? "",
        is_active: supplier ? (supplier.is_active ? "true" : "false") : "true",
      });
    }
  }, [isOpen, supplier, reset]);

  const submit = handleSubmit(async (values) => {
    await onSubmit({
      name: values.name,
      contact_name: values.contact_name || null,
      email: values.email || null,
      phone: values.phone || null,
      address: values.address || null,
      is_active: values.is_active ? values.is_active === "true" : undefined,
    });
  });

  return (
    <Drawer isOpen={isOpen} onClose={onClose} title={supplier ? "Edit Supplier" : "New Supplier"}>
      <form onSubmit={submit} className="space-y-4">
        <div>
          <Label htmlFor="name" required>
            Name
          </Label>
          <Input id="name" error={errors.name?.message} {...register("name")} />
        </div>
        <div>
          <Label htmlFor="contact_name">Contact name</Label>
          <Input id="contact_name" error={errors.contact_name?.message} {...register("contact_name")} />
        </div>
        <div>
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" error={errors.email?.message} {...register("email")} />
        </div>
        <div>
          <Label htmlFor="phone">Phone</Label>
          <Input id="phone" error={errors.phone?.message} {...register("phone")} />
        </div>
        <div>
          <Label htmlFor="address">Address</Label>
          <Input id="address" error={errors.address?.message} {...register("address")} />
        </div>
        {supplier && (
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
