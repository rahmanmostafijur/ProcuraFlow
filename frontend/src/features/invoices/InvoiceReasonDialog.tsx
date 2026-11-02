import { useId, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Label } from "@/components/ui/Label";
import { Modal } from "@/components/ui/Modal";
import { Textarea } from "@/components/ui/Textarea";

interface InvoiceReasonDialogProps {
  isOpen: boolean;
  title: string;
  subject: string;
  confirmLabel: string;
  isSubmitting?: boolean;
  onClose: () => void;
  onSubmit: (reason: string) => void;
}

const MAX_REASON = 500;

export function InvoiceReasonDialog(props: InvoiceReasonDialogProps) {
  return (
    <Modal isOpen={props.isOpen} onClose={props.onClose} title={props.title} size="sm">
      <ReasonForm {...props} />
    </Modal>
  );
}

// Mounted only while open, so each opening starts empty.
function ReasonForm({ subject, confirmLabel, isSubmitting, onClose, onSubmit }: InvoiceReasonDialogProps) {
  const fieldId = useId();
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = () => {
    const trimmed = reason.trim();
    if (trimmed === "") return setError("A reason is required");
    if (trimmed.length > MAX_REASON) return setError(`At most ${MAX_REASON} characters`);
    onSubmit(trimmed);
  };

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
      className="space-y-4"
    >
      <p className="text-sm text-text-secondary">{subject}</p>
      <div>
        <Label htmlFor={fieldId} required>
          Reason
        </Label>
        <Textarea
          id={fieldId}
          rows={3}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          error={error ?? undefined}
        />
      </div>
      <div className="flex justify-end gap-3">
        <Button type="button" variant="secondary" onClick={onClose} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button type="submit" variant="danger" disabled={isSubmitting}>
          {isSubmitting ? "Please wait…" : confirmLabel}
        </Button>
      </div>
    </form>
  );
}
