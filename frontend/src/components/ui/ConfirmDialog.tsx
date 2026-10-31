import { AlertTriangle } from "lucide-react";
import { type ReactNode, useId, useState } from "react";

import { Button } from "./Button";
import { Input } from "./Input";
import { Modal } from "./Modal";

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "primary" | "danger";
  isLoading?: boolean;
  /** When set, the user must type this exact text before the confirm button enables (irreversible actions). */
  confirmText?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

// Own component so the typed text resets every time the dialog opens: Modal unmounts its children when closed.
function ConfirmBody({
  message,
  confirmLabel,
  cancelLabel,
  variant,
  isLoading,
  confirmText,
  onConfirm,
  onCancel,
}: Omit<ConfirmDialogProps, "isOpen" | "title"> & { confirmLabel: string; cancelLabel: string; variant: string }) {
  const [typed, setTyped] = useState("");
  const inputId = useId();
  const matches = !confirmText || typed === confirmText;
  const isDanger = variant === "danger";

  return (
    <>
      <div className="flex gap-3">
        {isDanger && <AlertTriangle aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-danger-fg" />}
        <div className="text-sm text-text-secondary">{message}</div>
      </div>
      {confirmText && (
        <div className="mt-4">
          <label htmlFor={inputId} className="mb-1 block text-sm font-medium text-text-primary">
            Type <span className="font-semibold">{confirmText}</span> to confirm
          </label>
          <Input id={inputId} data-autofocus value={typed} onChange={(event) => setTyped(event.target.value)} />
        </div>
      )}
      <div className="mt-6 flex justify-end gap-3">
        {/* Cancel takes focus first for a destructive action so a stray Enter cannot confirm it. */}
        <Button
          variant="secondary"
          onClick={onCancel}
          disabled={isLoading}
          {...(!confirmText && isDanger ? { "data-autofocus": true } : {})}
        >
          {cancelLabel}
        </Button>
        <Button
          variant={isDanger ? "danger" : "primary"}
          onClick={onConfirm}
          disabled={!matches}
          loading={isLoading}
          {...(!confirmText && !isDanger ? { "data-autofocus": true } : {})}
        >
          {isLoading ? "Please wait…" : confirmLabel}
        </Button>
      </div>
    </>
  );
}

export function ConfirmDialog({
  isOpen,
  title,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "primary",
  ...rest
}: ConfirmDialogProps) {
  return (
    <Modal isOpen={isOpen} onClose={rest.onCancel} title={title} size="sm">
      <ConfirmBody confirmLabel={confirmLabel} cancelLabel={cancelLabel} variant={variant} {...rest} />
    </Modal>
  );
}
