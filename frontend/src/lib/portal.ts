import type { User } from "@/api/types";

const SUPPLIER_ROLE = "supplier";

/** Supplier accounts get 403 on every internal endpoint, so the internal shell must never render for them. */
export function isSupplierUser(user: User | null): boolean {
  return user !== null && (user.supplier_id != null || user.role.name === SUPPLIER_ROLE);
}
