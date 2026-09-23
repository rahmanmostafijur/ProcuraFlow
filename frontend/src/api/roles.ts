import { useQuery } from "@tanstack/react-query";

import { apiClient } from "./client";
import type { Role } from "./types";

export function useRoles() {
  return useQuery({
    queryKey: ["roles"],
    queryFn: async () => {
      const { data } = await apiClient.get<Role[]>("/roles");
      return data;
    },
  });
}
