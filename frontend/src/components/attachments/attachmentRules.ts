export const MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024;
const KILOBYTE = 1024;

export function formatFileSize(bytes: number): string {
  if (bytes < KILOBYTE) return `${bytes} B`;
  if (bytes < KILOBYTE * KILOBYTE) return `${(bytes / KILOBYTE).toFixed(1)} KB`;
  return `${(bytes / (KILOBYTE * KILOBYTE)).toFixed(1)} MB`;
}
