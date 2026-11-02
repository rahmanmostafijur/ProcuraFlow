import { Suspense, lazy } from "react";
import { Navigate } from "react-router-dom";

import { LoadingState } from "@/components/ui/LoadingState";
import { useAuth } from "@/lib/auth-context";
import { homePathFor } from "@/lib/portal";

// The public page is its own chunk, so signed-in users never download it.
const LandingPage = lazy(() => import("@/features/landing/LandingPage").then((m) => ({ default: m.LandingPage })));

/** "/" is the public landing page for visitors and a redirect to their home for signed-in users. */
export function LandingRoute() {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <LoadingState label="Loading ProcuraFlow…" />
      </div>
    );
  }

  if (user) {
    return <Navigate to={homePathFor(user)} replace />;
  }

  return (
    <Suspense fallback={<div className="min-h-screen bg-bg" />}>
      <LandingPage />
    </Suspense>
  );
}
