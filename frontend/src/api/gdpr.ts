import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "./client";
import { saveBlob } from "@/lib/download";

export type GdprSubject = "users" | "suppliers";

function subjectPath(subject: GdprSubject, id: number): string {
  return subject === "users" ? `/gdpr/users/${id}` : `/gdpr/suppliers/${id}/contact`;
}

/** The export is JSON; it is saved as a file rather than shown, since it holds personal data. */
export async function exportSubjectData(subject: GdprSubject, id: number): Promise<void> {
  const { data } = await apiClient.get<unknown>(`${subjectPath(subject, id)}/export`);
  saveBlob(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }), `gdpr-${subject}-${id}.json`);
}

export function useAnonymise(subject: GdprSubject) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await apiClient.post(`${subjectPath(subject, id)}/anonymise`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [subject] }),
  });
}
