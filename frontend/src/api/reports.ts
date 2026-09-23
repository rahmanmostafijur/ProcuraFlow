import { useQuery } from "@tanstack/react-query";

import { apiClient } from "./client";
import type { DelayedDelivery, SupplierPerformance } from "./types";

export function useSupplierPerformance() {
  return useQuery({
    queryKey: ["reports", "supplier-performance"],
    queryFn: async () => {
      const { data } = await apiClient.get<SupplierPerformance[]>("/reports/supplier-performance");
      return data;
    },
  });
}

export function useDelayedDeliveries() {
  return useQuery({
    queryKey: ["reports", "delayed-deliveries"],
    queryFn: async () => {
      const { data } = await apiClient.get<DelayedDelivery[]>("/reports/delayed-deliveries");
      return data;
    },
  });
}

export function useOnTimeDeliveryRate() {
  return useQuery({
    queryKey: ["reports", "on-time-delivery-rate"],
    queryFn: async () => {
      const { data } = await apiClient.get<{ on_time_percentage: number }>("/reports/on-time-delivery-rate");
      return data;
    },
  });
}

export function inventoryStatusCsvUrl(baseUrl: string): string {
  return `${baseUrl}/reports/inventory-status.csv`;
}
