import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { extractErrorMessage } from "@/api/client";
import { useRoles } from "@/api/roles";
import { useInviteUser } from "@/api/users";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";
import { useToast } from "@/components/ui/toast-context";

const schema = z.object({
  email: z.string().email("Enter a valid email"),
  full_name: z.string().min(1, "Name is required").max(255),
  role_id: z.string().min(1, "Select a role"),
});

type FormValues = z.infer<typeof schema>;

interface InviteUserModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function InviteUserModal({ isOpen, onClose }: InviteUserModalProps) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Invite user" size="sm">
      <InviteForm onClose={onClose} />
    </Modal>
  );
}

// Mounted only while the modal is open, so every opening starts with an empty form and no old error.
function InviteForm({ onClose }: { onClose: () => void }) {
  const { showToast } = useToast();
  const { data: roles } = useRoles();
  const inviteUser = useInviteUser();
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const submit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await inviteUser.mutateAsync({
        email: values.email,
        full_name: values.full_name,
        role_id: Number(values.role_id),
      });
      showToast(`Invitation sent to ${values.email}`);
      onClose();
    } catch (error) {
      setFormError(extractErrorMessage(error));
    }
  });

  return (
    <form onSubmit={(event) => void submit(event)} className="space-y-4">
      <p className="text-sm text-text-secondary">
        We email them a link to choose their own password. You never see or set it.
      </p>
      {formError && (
        <div role="alert" className="rounded-control bg-danger-bg px-3 py-2 text-sm text-danger-fg">
          {formError}
        </div>
      )}
      <div>
        <Label htmlFor="invite_email" required>
          Email
        </Label>
        <Input id="invite_email" type="email" error={errors.email?.message} {...register("email")} />
      </div>
      <div>
        <Label htmlFor="invite_full_name" required>
          Full name
        </Label>
        <Input id="invite_full_name" error={errors.full_name?.message} {...register("full_name")} />
      </div>
      <div>
        <Label htmlFor="invite_role_id" required>
          Role
        </Label>
        <Select id="invite_role_id" error={errors.role_id?.message} {...register("role_id")}>
          <option value="">Select a role</option>
          {roles?.map((role) => (
            <option key={role.id} value={role.id}>
              {role.name.replace(/_/g, " ")}
            </option>
          ))}
        </Select>
      </div>
      <div className="flex justify-end gap-3 pt-2">
        <Button type="button" variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <Button type="submit" disabled={inviteUser.isPending}>
          {inviteUser.isPending ? "Sending…" : "Send invitation"}
        </Button>
      </div>
    </form>
  );
}
