import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "./client";
import type { Attachment, AttachmentParentType } from "./types";

export function useAttachments(parentType: AttachmentParentType, parentId: number | undefined) {
  return useQuery({
    queryKey: ["attachments", parentType, parentId],
    queryFn: async () => {
      const { data } = await apiClient.get<Attachment[]>("/attachments", {
        params: { parent_type: parentType, parent_id: parentId },
      });
      return data;
    },
    enabled: parentId !== undefined,
  });
}

export function useUploadAttachment(parentType: AttachmentParentType, parentId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      const { data } = await apiClient.post<Attachment>("/attachments", form, {
        params: { parent_type: parentType, parent_id: parentId },
      });
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["attachments", parentType, parentId] }),
  });
}

export function useDeleteAttachment(parentType: AttachmentParentType, parentId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await apiClient.delete(`/attachments/${id}`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["attachments", parentType, parentId] }),
  });
}

/**
 * Download through the authenticated client: a plain link cannot work, because browsers navigate without the
 * Authorization header and the endpoint only serves people who may see the record.
 */
export async function downloadAttachment(attachment: Attachment): Promise<void> {
  const { data } = await apiClient.get<Blob>(`/attachments/${attachment.id}/download`, { responseType: "blob" });
  const objectUrl = URL.createObjectURL(data);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = attachment.filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
}
