import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useRoles } from "@/api/roles";
import type { User } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";

const schema = z.object({
  email: z.string().email("Enter a valid email"),
  full_name: z.string().min(1, "Name is required").max(255),
  password: z.string().min(8, "Password must be at least 8 characters").optional().or(z.literal("")),
  role_id: z.string().min(1, "Select a role"),
  is_active: z.enum(["true", "false"]).optional(),
});

type FormValues = z.infer<typeof schema>;

interface UserFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  user: User | null;
  onSubmit: (values: {
    email: string;
    full_name: string;
    password?: string;
    role_id: number;
    is_active?: boolean;
  }) => Promise<void>;
  isSubmitting: boolean;
}

export function UserFormModal({ isOpen, onClose, user, onSubmit, isSubmitting }: UserFormModalProps) {
  const { data: roles } = useRoles();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (isOpen) {
      reset({
        email: user?.email ?? "",
        full_name: user?.full_name ?? "",
        password: "",
        role_id: user ? String(user.role.id) : "",
        is_active: user ? (user.is_active ? "true" : "false") : "true",
      });
    }
  }, [isOpen, user, reset]);

  const submit = handleSubmit(async (values) => {
    await onSubmit({
      email: values.email,
      full_name: values.full_name,
      password: values.password || undefined,
      role_id: Number(values.role_id),
      is_active: values.is_active ? values.is_active === "true" : undefined,
    });
  });

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={user ? "Edit User" : "New User"} size="sm">
      <form onSubmit={submit} className="space-y-4">
        <div>
          <Label htmlFor="email" required>
            Email
          </Label>
          <Input
            id="email"
            type="email"
            disabled={Boolean(user)}
            error={errors.email?.message}
            {...register("email")}
          />
        </div>
        <div>
          <Label htmlFor="full_name" required>
            Full name
          </Label>
          <Input id="full_name" error={errors.full_name?.message} {...register("full_name")} />
        </div>
        <div>
          <Label htmlFor="password" required={!user}>
            {user ? "New password (optional)" : "Password"}
          </Label>
          <Input id="password" type="password" error={errors.password?.message} {...register("password")} />
        </div>
        <div>
          <Label htmlFor="role_id" required>
            Role
          </Label>
          <Select id="role_id" error={errors.role_id?.message} {...register("role_id")}>
            <option value="">Select a role</option>
            {roles?.map((role) => (
              <option key={role.id} value={role.id}>
                {role.name.replace(/_/g, " ")}
              </option>
            ))}
          </Select>
        </div>
        {user && (
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
    </Modal>
  );
}
