import { useState, type FormEvent } from "react";

import { extractErrorMessage } from "@/api/client";
import { useInvitePortalUser, usePortalUsers } from "@/api/supplierPortalAdmin";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { useToast } from "@/components/ui/toast-context";

export function SupplierPortalPanel({ supplierId }: { supplierId: number }) {
  const { showToast } = useToast();
  const { data: accounts, isLoading } = usePortalUsers(supplierId);
  const invite = useInvitePortalUser(supplierId);
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!/^\S+@\S+\.\S+$/.test(email.trim()) || !fullName.trim()) {
      setError("Enter the contact's name and a valid email address");
      return;
    }
    setError(null);
    try {
      await invite.mutateAsync({ email: email.trim(), full_name: fullName.trim() });
      showToast("Invitation sent");
      setEmail("");
      setFullName("");
    } catch (failure) {
      setError(extractErrorMessage(failure));
    }
  };

  return (
    <Card className="space-y-4 p-6">
      <div>
        <h2 className="text-base font-semibold text-text-primary">Supplier portal</h2>
        <p className="text-sm text-text-secondary">
          Invite a contact to see this supplier's orders, send invoices and keep documents current.
        </p>
      </div>
      {isLoading && <p className="text-sm text-text-secondary">Loading portal accounts…</p>}
      {accounts?.length === 0 && <p className="text-sm text-text-secondary">Nobody has been invited yet.</p>}
      <ul className="divide-y divide-border text-sm">
        {accounts?.map((account) => (
          <li key={account.id} className="flex items-center justify-between py-2">
            <span>
              <span className="font-medium text-text-primary">{account.full_name}</span>{" "}
              <span className="text-text-secondary">{account.email}</span>
            </span>
            <StatusBadge
              status={account.is_active ? "active" : "inactive"}
              label={account.is_active ? "Active" : "Inactive"}
            />
          </li>
        ))}
      </ul>
      <form
        onSubmit={(event) => void submit(event)}
        className="grid gap-3 sm:grid-cols-2"
        aria-label="Invite a portal user"
      >
        <div>
          <Label htmlFor="portal-name">Contact name</Label>
          <Input id="portal-name" value={fullName} onChange={(event) => setFullName(event.target.value)} />
        </div>
        <div>
          <Label htmlFor="portal-email">Contact email</Label>
          <Input id="portal-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
        </div>
        {error && (
          <p role="alert" className="text-sm text-danger-fg sm:col-span-2">
            {error}
          </p>
        )}
        <div className="sm:col-span-2">
          <Button type="submit" disabled={invite.isPending}>
            {invite.isPending ? "Sending…" : "Send invitation"}
          </Button>
        </div>
      </form>
    </Card>
  );
}
