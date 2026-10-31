import { apiClient } from "./client";
import { saveBlob } from "@/lib/download";

/**
 * Fetches a file through the authenticated client and hands it to the browser. A plain link cannot work: browsers
 * navigate without the Authorization header. The error body of a blob request is a Blob, so callers show a fixed message.
 */
export async function downloadFile(path: string, filename: string, params?: Record<string, string>): Promise<void> {
  const { data } = await apiClient.get<Blob>(path, { params, responseType: "blob" });
  saveBlob(data, filename);
}
