import type { User } from "@/api/types";

const SUPPLIER_ROLE = "supplier";

export const DASHBOARD_PATH = "/dashboard";
export const PORTAL_PATH = "/portal";

/** Where a signed-in user belongs: the portal for supplier accounts, the dashboard for everyone else. */
export function homePathFor(user: User | null): string {
  return isSupplierUser(user) ? PORTAL_PATH : DASHBOARD_PATH;
}

/** Supplier accounts get 403 on every internal endpoint, so the internal shell must never render for them. */
export function isSupplierUser(user: User | null): boolean {
  return user !== null && (user.supplier_id != null || user.role.name === SUPPLIER_ROLE);
}
