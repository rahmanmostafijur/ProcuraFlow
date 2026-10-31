import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "@/lib/auth-context";
import { isSupplierUser } from "@/lib/portal";

/** Keeps supplier accounts out of the internal app: every internal endpoint answers them with 403. */
export function InternalRoute() {
  const { user } = useAuth();

  if (isSupplierUser(user)) {
    return <Navigate to="/portal" replace />;
  }

  return <Outlet />;
}
