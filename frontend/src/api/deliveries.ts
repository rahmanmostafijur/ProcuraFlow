import { useQuery } from "@tanstack/react-query";

import { apiClient } from "./client";
import type { Delivery, PaginatedResponse } from "./types";

export function useDeliveries(page: number, pageSize: number) {
  return useQuery({
    queryKey: ["deliveries", page, pageSize],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<Delivery>>("/deliveries", {
        params: { page, page_size: pageSize },
      });
      return data;
    },
  });
}
