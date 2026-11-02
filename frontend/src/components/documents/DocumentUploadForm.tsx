import { useRef, useState, type FormEvent } from "react";

import { DOCUMENT_TYPE_LABELS, type DocumentUploadInput, type SupplierDocumentType } from "@/api/supplierDocuments";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Select } from "@/components/ui/Select";

interface DocumentUploadFormProps {
  isPending: boolean;
  /** Resolves once the upload succeeded, so the form can clear itself. */
  onSubmit: (input: DocumentUploadInput) => Promise<void>;
}

const TYPES = Object.keys(DOCUMENT_TYPE_LABELS) as SupplierDocumentType[];

export function DocumentUploadForm({ isPending, onSubmit }: DocumentUploadFormProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [documentType, setDocumentType] = useState<SupplierDocumentType>("w9");
  const [issueDate, setIssueDate] = useState("");
  const [expiryDate, setExpiryDate] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setError("Choose a file to upload");
      return;
    }
    if (issueDate && expiryDate && expiryDate < issueDate) {
      setError("The expiry date cannot be before the issue date");
      return;
    }
    setError(null);
    try {
      await onSubmit({
        file,
        document_type: documentType,
        issue_date: issueDate || undefined,
        expiry_date: expiryDate || undefined,
      });
    } catch {
      return; // the caller already told the person why
    }
    setIssueDate("");
    setExpiryDate("");
    if (fileRef.current) fileRef.current.value = "";
  };

  return (
    <form onSubmit={(event) => void submit(event)} className="grid gap-3 sm:grid-cols-2">
      <div>
        <Label htmlFor="doc-type">Document type</Label>
        <Select
          id="doc-type"
          value={documentType}
          onChange={(event) => setDocumentType(event.target.value as SupplierDocumentType)}
        >
          {TYPES.map((type) => (
            <option key={type} value={type}>
              {DOCUMENT_TYPE_LABELS[type]}
            </option>
          ))}
        </Select>
      </div>
      <div>
        <Label htmlFor="doc-file">File</Label>
        <input
          ref={fileRef}
          id="doc-file"
          type="file"
          accept="application/pdf,image/png,image/jpeg"
          className="block w-full text-sm"
        />
      </div>
      <div>
        <Label htmlFor="doc-issued">Issued on</Label>
        <Input id="doc-issued" type="date" value={issueDate} onChange={(event) => setIssueDate(event.target.value)} />
      </div>
      <div>
        <Label htmlFor="doc-expires">Expires on</Label>
        <Input
          id="doc-expires"
          type="date"
          value={expiryDate}
          onChange={(event) => setExpiryDate(event.target.value)}
        />
      </div>
      {error && (
        <p role="alert" className="text-sm text-danger-fg sm:col-span-2">
          {error}
        </p>
      )}
      <div className="sm:col-span-2">
        <Button type="submit" disabled={isPending}>
          {isPending ? "Uploading…" : "Upload document"}
        </Button>
      </div>
    </form>
  );
}
