import { ImageUp, Trash2 } from "lucide-react";
import { type ChangeEvent, useId, useRef } from "react";

import { extractErrorMessage } from "@/api/client";
import { absoluteLogoUrl, useRemoveLogo, useUploadLogo } from "@/api/companySettings";
import type { CompanySettings } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/toast-context";

const MAX_LOGO_BYTES = 1024 * 1024;
const ACCEPTED_TYPES = "image/png,image/jpeg";

export function LogoUploader({ settings }: { settings: CompanySettings }) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const { showToast } = useToast();
  const uploadLogo = useUploadLogo();
  const removeLogo = useRemoveLogo();
  const logo = absoluteLogoUrl(settings.logo_url);

  const handleFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (file.size > MAX_LOGO_BYTES) {
      showToast("The logo must be 1 MB or smaller.", "error");
      return;
    }
    try {
      await uploadLogo.mutateAsync(file);
      showToast("Logo updated");
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  const handleRemove = async () => {
    try {
      await removeLogo.mutateAsync();
      showToast("Logo removed");
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-4">
      <div className="flex h-16 w-16 items-center justify-center overflow-hidden rounded-card border border-border bg-bg">
        {logo ? (
          <img src={logo} alt="Current company logo" className="h-full w-full object-contain" />
        ) : (
          <span className="text-xs text-text-muted">No logo</span>
        )}
      </div>
      <div className="space-y-2">
        <div className="flex gap-2">
          <input
            ref={inputRef}
            id={inputId}
            type="file"
            aria-label="Choose a logo file"
            accept={ACCEPTED_TYPES}
            className="sr-only"
            onChange={(event) => void handleFile(event)}
          />
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => inputRef.current?.click()}
            disabled={uploadLogo.isPending}
          >
            <ImageUp className="h-4 w-4" /> {uploadLogo.isPending ? "Uploading…" : "Upload logo"}
          </Button>
          {logo && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => void handleRemove()}
              disabled={removeLogo.isPending}
            >
              <Trash2 className="h-4 w-4" /> Remove
            </Button>
          )}
        </div>
        <p className="text-xs text-text-secondary">PNG or JPEG, up to 1 MB. Used in the app, on PDFs and in emails.</p>
      </div>
    </div>
  );
}
