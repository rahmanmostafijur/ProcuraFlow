import { AlertCircle, CheckCircle2, FileText, UploadCloud, X } from "lucide-react";
import { type ChangeEvent, type DragEvent, useId, useRef, useState } from "react";

import { cn } from "@/lib/utils";

import { type FileRejection, type FileRules, formatFileSize, partitionFiles } from "./file-validation";
import { FOCUS_RING } from "./focus";
import { IconButton } from "./IconButton";

export interface DropzoneItem {
  id: string;
  name: string;
  size: number;
  /** 0 to 100 while uploading. */
  progress?: number;
  status?: "uploading" | "done" | "error";
  error?: string;
}

interface FileDropzoneProps extends FileRules {
  /** Called with the files that passed validation. The parent uploads them and reports back through `items`. */
  onFilesAccepted: (files: File[]) => void;
  onFilesRejected?: (rejected: FileRejection[]) => void;
  items?: DropzoneItem[];
  onRemove?: (id: string) => void;
  multiple?: boolean;
  disabled?: boolean;
  label?: string;
}

function ItemRow({ item, onRemove }: { item: DropzoneItem; onRemove?: (id: string) => void }) {
  const Icon = item.status === "error" ? AlertCircle : item.status === "done" ? CheckCircle2 : FileText;
  return (
    <li className="flex items-center gap-3 rounded-control border border-border bg-surface px-3 py-2 text-sm">
      <Icon
        aria-hidden="true"
        className={cn("h-4 w-4 shrink-0", item.status === "error" ? "text-danger-fg" : "text-text-secondary")}
      />
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium text-text-primary">{item.name}</p>
        <p className="text-xs text-text-secondary">
          {formatFileSize(item.size)}
          {item.status === "done" && " · Uploaded"}
          {item.status === "error" && ` · ${item.error ?? "Upload failed"}`}
        </p>
        {item.status === "uploading" && (
          <progress
            max={100}
            value={item.progress ?? 0}
            aria-label={`Uploading ${item.name}`}
            className="mt-1 h-1.5 w-full accent-brand"
          />
        )}
      </div>
      {onRemove && (
        <IconButton
          size="sm"
          aria-label={`Remove ${item.name}`}
          icon={<X className="h-4 w-4" />}
          onClick={() => onRemove(item.id)}
        />
      )}
    </li>
  );
}

/**
 * The real control is a visually hidden file input inside a label, so click, Enter and Space open the picker and the
 * browser handles focus. The label draws the focus ring through :focus-within. Dropped files go through the same check.
 */
export function FileDropzone({
  onFilesAccepted,
  onFilesRejected,
  items = [],
  onRemove,
  multiple = true,
  disabled,
  label = "Upload files",
  accept,
  maxSizeBytes,
}: FileDropzoneProps) {
  const hintId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [rejected, setRejected] = useState<FileRejection[]>([]);

  const handle = (files: File[]) => {
    const picked = multiple ? files : files.slice(0, 1);
    const result = partitionFiles(picked, { accept, maxSizeBytes });
    setRejected(result.rejected);
    if (result.rejected.length) onFilesRejected?.(result.rejected);
    if (result.accepted.length) onFilesAccepted(result.accepted);
  };

  const onChange = (event: ChangeEvent<HTMLInputElement>) => {
    handle(Array.from(event.target.files ?? []));
    // Reset so choosing the same file again still fires change.
    event.target.value = "";
  };

  const onDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setDragging(false);
    if (!disabled) handle(Array.from(event.dataTransfer.files));
  };

  const hint = [
    accept?.length ? `Allowed: ${accept.join(", ")}` : null,
    maxSizeBytes ? `up to ${formatFileSize(maxSizeBytes)} each` : null,
  ]
    .filter(Boolean)
    .join(", ");

  return (
    <div className="space-y-3">
      <label
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "flex cursor-pointer flex-col items-center gap-2 rounded-card border-2 border-dashed px-6 py-8 text-center transition-colors duration-fast ease-standard",
          "focus-within:ring-2 focus-within:ring-focus focus-within:ring-offset-2 focus-within:ring-offset-surface",
          dragging ? "border-brand bg-brand-subtle" : "border-border-strong bg-surface hover:bg-bg",
          disabled && "cursor-not-allowed opacity-60",
        )}
      >
        <UploadCloud aria-hidden="true" className="h-8 w-8 text-text-secondary" />
        <span className="text-sm font-semibold text-text-primary">{dragging ? "Drop to upload" : label}</span>
        <span className="text-sm text-text-secondary">Drag files here or choose them from your device</span>
        <input
          ref={inputRef}
          type="file"
          className="sr-only"
          multiple={multiple}
          disabled={disabled}
          accept={accept?.join(",")}
          aria-describedby={hint ? hintId : undefined}
          onChange={onChange}
        />
        {hint && (
          <span id={hintId} className="text-xs text-text-secondary">
            {hint}
          </span>
        )}
      </label>
      {rejected.length > 0 && (
        <ul role="alert" className="space-y-1">
          {rejected.map((item, index) => (
            <li key={`${item.name}-${index}`} className="flex items-start gap-1.5 text-sm font-medium text-danger-fg">
              <AlertCircle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                {item.name}: {item.reason}
              </span>
            </li>
          ))}
        </ul>
      )}
      {items.length > 0 && (
        <ul aria-label="Selected files" className={cn("space-y-2", FOCUS_RING)}>
          {items.map((item) => (
            <ItemRow key={item.id} item={item} onRemove={onRemove} />
          ))}
        </ul>
      )}
    </div>
  );
}
