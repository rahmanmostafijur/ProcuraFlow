import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "./client";
import type { PaginatedResponse, User } from "./types";

export interface UserInput {
  email: string;
  full_name: string;
  password: string;
  role_id: number;
}

export function useUsers(page: number, pageSize: number, search?: string) {
  return useQuery({
    queryKey: ["users", page, pageSize, search],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<User>>("/users", {
        params: { page, page_size: pageSize, search },
      });
      return data;
    },
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: UserInput) => {
      const { data } = await apiClient.post<User>("/users", input);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      ...input
    }: {
      id: number;
      full_name?: string;
      role_id?: number;
      is_active?: boolean;
      password?: string;
    }) => {
      const { data } = await apiClient.patch<User>(`/users/${id}`, input);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });
}
