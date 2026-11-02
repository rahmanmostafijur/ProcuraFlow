import { useQuery } from "@tanstack/react-query";

import { apiClient } from "./client";

export interface DemoAccount {
  /** The value to send to the demo sign-in. */
  role: string;
  role_name: string;
  full_name: string;
  email: string;
  description: string;
  /** Supplier accounts land in the supplier portal. */
  is_portal: boolean;
}

/** Answers 404 unless the server runs in demo mode, in which case the query ends in an error and nothing renders. */
export function useDemoAccounts(enabled: boolean) {
  return useQuery({
    queryKey: ["demo-accounts"],
    queryFn: async () => {
      const { data } = await apiClient.get<DemoAccount[]>("/auth/demo-accounts");
      return data;
    },
    enabled,
    retry: false,
    staleTime: Infinity,
  });
}
