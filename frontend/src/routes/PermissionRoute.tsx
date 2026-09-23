import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "@/lib/auth-context";

export function PermissionRoute({ permission }: { permission: string }) {
  const { hasPermission } = useAuth();

  if (!hasPermission(permission)) {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}
