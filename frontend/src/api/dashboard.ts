import { useQuery } from "@tanstack/react-query";

import { apiClient } from "./client";
import type { DashboardSummary, MonthlyTrendPoint, RecentActivityItem } from "./types";

export function useDashboardSummary() {
  return useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: async () => {
      const { data } = await apiClient.get<DashboardSummary>("/dashboard/summary");
      return data;
    },
  });
}

export function useMonthlyTrends(months = 6) {
  return useQuery({
    queryKey: ["dashboard", "monthly-trends", months],
    queryFn: async () => {
      const { data } = await apiClient.get<MonthlyTrendPoint[]>("/dashboard/monthly-trends", {
        params: { months },
      });
      return data;
    },
  });
}

export function useRecentActivity(limit = 10) {
  return useQuery({
    queryKey: ["dashboard", "recent-activity", limit],
    queryFn: async () => {
      const { data } = await apiClient.get<RecentActivityItem[]>("/dashboard/recent-activity", {
        params: { limit },
      });
      return data;
    },
  });
}
