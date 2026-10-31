import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "./client";

export interface AppNotification {
  id: number;
  message: string;
  is_read: boolean;
  created_at: string;
}

const POLL_INTERVAL_MS = 60_000;

export function useUnreadCount() {
  return useQuery({
    queryKey: ["notifications", "unread-count"],
    queryFn: async () => {
      const { data } = await apiClient.get<{ unread: number }>("/notifications/unread-count");
      return data.unread;
    },
    refetchInterval: POLL_INTERVAL_MS,
  });
}

export function useNotifications(enabled: boolean) {
  return useQuery({
    queryKey: ["notifications", "list"],
    queryFn: async () => {
      const { data } = await apiClient.get<AppNotification[]>("/notifications");
      return data;
    },
    enabled,
  });
}

export function useMarkNotificationRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await apiClient.post(`/notifications/${id}/read`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });
}

export function useMarkAllNotificationsRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await apiClient.post("/notifications/read-all");
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });
}
