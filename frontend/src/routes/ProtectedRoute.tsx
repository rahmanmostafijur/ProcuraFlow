import { Navigate, Outlet } from "react-router-dom";

import { LoadingState } from "@/components/ui/LoadingState";
import { useAuth } from "@/lib/auth-context";

export function ProtectedRoute() {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <LoadingState label="Loading ProcuraFlow…" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
