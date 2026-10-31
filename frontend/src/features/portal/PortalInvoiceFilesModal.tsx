import { Download } from "lucide-react";
import { useRef } from "react";

import { extractErrorMessage } from "@/api/client";
import {
  downloadPortalInvoiceFile,
  usePortalInvoiceFiles,
  useUploadPortalInvoiceFile,
  type PortalInvoice,
} from "@/api/portal";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/toast-context";

export function PortalInvoiceFilesModal({ invoice, onClose }: { invoice: PortalInvoice | null; onClose: () => void }) {
  const { showToast } = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const { data: files } = usePortalInvoiceFiles(invoice?.id ?? null);
  const upload = useUploadPortalInvoiceFile(invoice?.id ?? 0);

  const attach = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    try {
      await upload.mutateAsync(file);
      showToast("File attached");
      if (fileRef.current) fileRef.current.value = "";
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  return (
    <Modal isOpen={invoice !== null} onClose={onClose} title={`Files for ${invoice?.invoice_number ?? ""}`} size="md">
      {files?.length === 0 && <p className="text-sm text-slate-500">No files attached.</p>}
      <ul className="divide-y divide-slate-100">
        {files?.map((file) => (
          <li key={file.id} className="flex items-center justify-between py-2 text-sm">
            <span className="truncate">{file.filename}</span>
            <Button
              variant="ghost"
              size="sm"
              aria-label={`Download ${file.filename}`}
              onClick={() =>
                void downloadPortalInvoiceFile(invoice!.id, file).catch(() =>
                  showToast("The file could not be downloaded. Please try again.", "error"),
                )
              }
            >
              <Download className="h-4 w-4" />
            </Button>
          </li>
        ))}
      </ul>
      {invoice?.status === "draft" && (
        <div className="mt-4 flex items-center gap-3">
          <input
            ref={fileRef}
            type="file"
            aria-label="Choose a file to attach"
            accept="application/pdf,image/png,image/jpeg"
            className="block flex-1 text-sm"
          />
          <Button variant="secondary" disabled={upload.isPending} onClick={() => void attach()}>
            {upload.isPending ? "Uploading…" : "Attach file"}
          </Button>
        </div>
      )}
    </Modal>
  );
}
