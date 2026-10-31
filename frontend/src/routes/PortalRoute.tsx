import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "@/lib/auth-context";
import { isSupplierUser } from "@/lib/portal";

/** The supplier portal is for supplier accounts only; everyone else belongs in the internal app. */
export function PortalRoute() {
  const { user } = useAuth();

  if (!isSupplierUser(user)) {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}
