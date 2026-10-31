import { formatNumber } from "@/lib/format";

export interface FileRules {
  /** Extensions (".pdf") and MIME types ("image/png", "image/*"), like the input accept attribute. */
  accept?: string[];
  maxSizeBytes?: number;
}

export interface FileRejection {
  name: string;
  reason: string;
}

const KB = 1024;
const MB = KB * 1024;

export function formatFileSize(bytes: number): string {
  if (bytes >= MB) return formatNumber(bytes / MB, { style: "unit", unit: "megabyte", maximumFractionDigits: 1 });
  if (bytes >= KB) return formatNumber(bytes / KB, { style: "unit", unit: "kilobyte", maximumFractionDigits: 0 });
  return formatNumber(bytes, { style: "unit", unit: "byte" });
}

function matchesAccept(file: File, accept: string[]): boolean {
  const name = file.name.toLowerCase();
  return accept.some((rule) => {
    const wanted = rule.trim().toLowerCase();
    if (wanted.startsWith(".")) return name.endsWith(wanted);
    if (wanted.endsWith("/*")) return file.type.toLowerCase().startsWith(wanted.slice(0, -1));
    return file.type.toLowerCase() === wanted;
  });
}

/** An empty file is always refused: it is nearly always a failed export, and some servers reject it anyway. */
export function validateFile(file: File, { accept, maxSizeBytes }: FileRules): string | null {
  if (file.size === 0) return "The file is empty.";
  if (accept?.length && !matchesAccept(file, accept)) return `Only ${accept.join(", ")} files are allowed.`;
  if (maxSizeBytes !== undefined && file.size > maxSizeBytes) {
    return `The file is larger than ${formatFileSize(maxSizeBytes)}.`;
  }
  return null;
}

export function partitionFiles(files: File[], rules: FileRules): { accepted: File[]; rejected: FileRejection[] } {
  const accepted: File[] = [];
  const rejected: FileRejection[] = [];
  for (const file of files) {
    const reason = validateFile(file, rules);
    if (reason) rejected.push({ name: file.name, reason });
    else accepted.push(file);
  }
  return { accepted, rejected };
}
