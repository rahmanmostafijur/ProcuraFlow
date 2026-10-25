import { Download, Paperclip, Trash2 } from "lucide-react";
import { useId, useRef, type ChangeEvent } from "react";

import { extractErrorMessage } from "@/api/client";
import { downloadAttachment, useAttachments, useDeleteAttachment, useUploadAttachment } from "@/api/attachments";
import type { Attachment, AttachmentParentType } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useToast } from "@/components/ui/toast-context";
import { formatDateTime } from "@/lib/utils";

import { MAX_ATTACHMENT_BYTES, formatFileSize } from "./attachmentRules";

interface AttachmentsProps {
  parentType: AttachmentParentType;
  parentId: number;
  /** Whether the signed-in user may add and remove files; the API has the final say and its refusal is shown. */
  canWrite: boolean;
}

export function Attachments({ parentType, parentId, canWrite }: AttachmentsProps) {
  const { showToast } = useToast();
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const { data: attachments, isLoading, isError } = useAttachments(parentType, parentId);
  const upload = useUploadAttachment(parentType, parentId);
  const remove = useDeleteAttachment(parentType, parentId);

  const handleFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.size > MAX_ATTACHMENT_BYTES) {
      showToast("That file is larger than 10 MB. Choose a smaller PDF, PNG or JPEG.", "error");
    } else {
      try {
        await upload.mutateAsync(file);
        showToast("File attached");
      } catch (error) {
        showToast(extractErrorMessage(error), "error");
      }
    }
    if (inputRef.current) inputRef.current.value = "";
  };

  const handleDownload = async (attachment: Attachment) => {
    try {
      await downloadAttachment(attachment);
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  const handleRemove = async (attachment: Attachment) => {
    try {
      await remove.mutateAsync(attachment.id);
      showToast("File removed");
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  return (
    <Card className="p-5">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-slate-900">Attachments</h2>
        {canWrite && (
          <div>
            <input
              ref={inputRef}
              id={inputId}
              type="file"
              accept="application/pdf,image/png,image/jpeg"
              className="sr-only"
              aria-label="Choose a file to attach"
              onChange={(event) => void handleFile(event)}
            />
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={upload.isPending}
              onClick={() => inputRef.current?.click()}
            >
              <Paperclip className="h-3.5 w-3.5" /> {upload.isPending ? "Uploading…" : "Attach file"}
            </Button>
          </div>
        )}
      </div>
      {canWrite && <p className="mb-3 text-xs text-slate-500">PDF, PNG or JPEG, up to 10 MB each.</p>}
      {isLoading && <p className="text-sm text-slate-500">Loading attachments…</p>}
      {isError && <p className="text-sm text-red-600">The attachments could not be loaded.</p>}
      {attachments && attachments.length === 0 && <p className="text-sm text-slate-500">No files attached.</p>}
      <ul className="divide-y divide-slate-100">
        {attachments?.map((attachment) => (
          <li key={attachment.id} className="flex items-center justify-between gap-3 py-2 text-sm">
            <div className="min-w-0">
              <p className="truncate font-medium text-slate-800">{attachment.filename}</p>
              <p className="text-xs text-slate-500">
                {formatFileSize(attachment.size_bytes)} · {attachment.uploaded_by.full_name} ·{" "}
                {formatDateTime(attachment.created_at)}
              </p>
            </div>
            <div className="flex shrink-0 gap-1">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                aria-label={`Download ${attachment.filename}`}
                onClick={() => void handleDownload(attachment)}
              >
                <Download className="h-4 w-4" />
              </Button>
              {canWrite && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  aria-label={`Remove ${attachment.filename}`}
                  disabled={remove.isPending}
                  onClick={() => void handleRemove(attachment)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}
