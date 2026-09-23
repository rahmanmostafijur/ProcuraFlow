import { useQuery } from "@tanstack/react-query";

import { apiClient } from "./client";
import type { AuditLog, PaginatedResponse } from "./types";

export function useAuditLogs(page: number, pageSize: number, entityType?: string) {
  return useQuery({
    queryKey: ["audit-logs", page, pageSize, entityType],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<AuditLog>>("/audit-logs", {
        params: { page, page_size: pageSize, entity_type: entityType },
      });
      return data;
    },
  });
}
