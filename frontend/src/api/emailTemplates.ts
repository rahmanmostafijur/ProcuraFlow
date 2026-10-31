import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "./client";

export interface EmailTemplate {
  key: string;
  label: string;
  variables: string[];
  subject: string;
  body: string;
  is_customised: boolean;
  default_subject: string;
  default_body: string;
}

export function useEmailTemplates() {
  return useQuery({
    queryKey: ["email-templates"],
    queryFn: async () => {
      const { data } = await apiClient.get<EmailTemplate[]>("/email-templates");
      return data;
    },
  });
}

export function useSaveEmailTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ key, ...input }: { key: string; subject: string; body: string }) => {
      const { data } = await apiClient.put<EmailTemplate>(`/email-templates/${key}`, input);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["email-templates"] }),
  });
}

export function useResetEmailTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (key: string) => {
      const { data } = await apiClient.delete<EmailTemplate>(`/email-templates/${key}`);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["email-templates"] }),
  });
}
