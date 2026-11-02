import { useId, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/Button";
import { Label } from "@/components/ui/Label";
import { Modal } from "@/components/ui/Modal";
import { Textarea } from "@/components/ui/Textarea";

interface DecisionDialogProps {
  isOpen: boolean;
  mode: "approve" | "reject";
  /** What is being decided, e.g. "REQ-0001 · Laptops". */
  subject: string;
  /** Extra explanation shown above the comment box. */
  notice?: ReactNode;
  isSubmitting?: boolean;
  onClose: () => void;
  onSubmit: (comment: string) => void;
}

const MAX_COMMENT = 500;

export function DecisionDialog(props: DecisionDialogProps) {
  return (
    <Modal
      isOpen={props.isOpen}
      onClose={props.onClose}
      title={props.mode === "reject" ? "Reject" : "Approve"}
      size="sm"
    >
      <DecisionForm {...props} />
    </Modal>
  );
}

// Mounted only while the dialog is open, so every opening starts with an empty comment.
function DecisionForm({ mode, subject, notice, isSubmitting, onClose, onSubmit }: DecisionDialogProps) {
  const fieldId = useId();
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const isReject = mode === "reject";

  const submit = () => {
    const trimmed = comment.trim();
    if (isReject && trimmed === "") {
      setError("A comment is required to reject");
      return;
    }
    if (trimmed.length > MAX_COMMENT) {
      setError(`At most ${MAX_COMMENT} characters`);
      return;
    }
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
      {notice && <p className="text-sm text-text-secondary">{notice}</p>}
      <div>
        <Label htmlFor={fieldId} required={isReject}>
          {isReject ? "Reason for rejecting" : "Comment (optional)"}
        </Label>
        <Textarea
          id={fieldId}
          rows={3}
          value={comment}
          onChange={(event) => setComment(event.target.value)}
          error={error ?? undefined}
        />
      </div>
      <div className="flex justify-end gap-3">
        <Button type="button" variant="secondary" onClick={onClose} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button type="submit" variant={isReject ? "danger" : "primary"} disabled={isSubmitting}>
          {isSubmitting ? "Please wait…" : isReject ? "Reject" : "Approve"}
        </Button>
      </div>
    </form>
  );
}
