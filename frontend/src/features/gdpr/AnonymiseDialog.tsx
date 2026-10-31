import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Modal } from "@/components/ui/Modal";

export const CONFIRM_WORD = "ANONYMISE";

interface AnonymiseDialogProps {
  /** Who is affected, shown in the warning. Null keeps the dialog closed. */
  subjectName: string | null;
  isLoading: boolean;
  /** The server's refusal (for example "the last active admin"), shown until the next attempt. */
  error: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}

/** Anonymising cannot be undone, so the button only works once the confirmation word has been typed. */
export function AnonymiseDialog({ subjectName, isLoading, error, onConfirm, onCancel }: AnonymiseDialogProps) {
  const [typed, setTyped] = useState("");
  const close = () => {
    setTyped("");
    onCancel();
  };

  return (
    <Modal isOpen={subjectName !== null} onClose={close} title="Anonymise personal data" size="sm">
      <p className="text-sm text-slate-600">
        This replaces the name and email of <strong>{subjectName}</strong> with placeholders. Financial records stay. It
        cannot be undone.
      </p>
      <div className="mt-4">
        <Label htmlFor="gdpr-confirm">{`Type ${CONFIRM_WORD} to confirm`}</Label>
        <Input id="gdpr-confirm" value={typed} onChange={(event) => setTyped(event.target.value)} />
      </div>
      {error && (
        <p role="alert" className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
      <div className="mt-6 flex justify-end gap-3">
        <Button variant="secondary" onClick={close} disabled={isLoading}>
          Cancel
        </Button>
        <Button variant="danger" disabled={typed !== CONFIRM_WORD || isLoading} onClick={onConfirm}>
          {isLoading ? "Please wait…" : "Anonymise"}
        </Button>
      </div>
    </Modal>
  );
}
