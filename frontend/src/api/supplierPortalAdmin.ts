import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "./client";

export interface PortalAccount {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  created_at: string;
}

export interface PortalInviteInput {
  email: string;
  full_name: string;
}

export function usePortalUsers(supplierId: number) {
  return useQuery({
    queryKey: ["portal-users", supplierId],
    queryFn: async () => {
      const { data } = await apiClient.get<PortalAccount[]>(`/suppliers/${supplierId}/portal-users`);
      return data;
    },
  });
}

export function useInvitePortalUser(supplierId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: PortalInviteInput) => {
      const { data } = await apiClient.post<PortalAccount>(`/suppliers/${supplierId}/portal-invite`, input);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["portal-users", supplierId] }),
  });
}
