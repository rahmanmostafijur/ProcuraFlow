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

const INVENTORY_CSV_FILENAME = "inventory-status.csv";

/**
 * Download the inventory CSV through the authenticated client. A plain link cannot work: browsers
 * navigate without the Authorization header, and the endpoint requires a signed-in user.
 */
export async function downloadInventoryStatusCsv(): Promise<void> {
  const { data } = await apiClient.get<Blob>("/reports/inventory-status.csv", { responseType: "blob" });
  const objectUrl = URL.createObjectURL(data);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = INVENTORY_CSV_FILENAME;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
}
