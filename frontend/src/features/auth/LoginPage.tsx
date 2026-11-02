import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";

import { extractErrorMessage } from "@/api/client";
import { useBranding } from "@/api/companySettings";
import { CompanyMark } from "@/components/layout/CompanyMark";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { useAuth } from "@/lib/auth-context";
import { homePathFor } from "@/lib/portal";
import { useApplyBrandColor } from "@/lib/use-brand-color";
import { type BackendStatus, useBackendReadiness } from "@/lib/use-backend-readiness";

import { BackendStatusNotice } from "./BackendStatusNotice";

const loginSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

type LoginFormValues = z.infer<typeof loginSchema>;

const SUBMIT_LABELS: Record<BackendStatus, string> = {
  checking: "Connecting…",
  waking: "Waiting for server…",
  ready: "Sign in",
  unavailable: "Sign in",
};

export function LoginPage() {
  const { login, user, isLoading } = useAuth();
  const navigate = useNavigate();
  // Set by the reset, invitation and change-password flows when they send the user here.
  const notice = (useLocation().state as { notice?: string } | null)?.notice;
  const [formError, setFormError] = useState<string | null>(null);
  const backend = useBackendReadiness();
  // Only asked once the API answers, so a sleeping backend shows the waking notice instead of a failed request.
  const { data: branding } = useBranding(backend.status === "ready");
  useApplyBrandColor(branding?.brand_color);
  const companyName = branding?.company_name ?? "ProcuraFlow";

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({ resolver: zodResolver(loginSchema) });

  if (!isLoading && user) {
    return <Navigate to={homePathFor(user)} replace />;
  }

  const onSubmit = async (values: LoginFormValues) => {
    setFormError(null);
    try {
      await login(values.email, values.password);
      // The landing page at "/" sends the signed-in user to the right home.
      void navigate("/");
    } catch (error) {
      setFormError(extractErrorMessage(error));
    }
  };

  const isBackendReady = backend.status === "ready";

  return (
    <div className="flex min-h-screen bg-bg">
      <aside className="hidden flex-1 flex-col justify-between bg-brand p-12 text-on-brand lg:flex">
        <div className="inline-flex self-start rounded-card bg-surface p-3">
          <CompanyMark branding={branding} size="lg" />
        </div>
        <div className="max-w-md space-y-3">
          <p className="text-display-md">From purchase request to paid invoice, in one place.</p>
          <p className="text-body opacity-90">Procurement, inventory &amp; delivery management.</p>
        </div>
      </aside>

      <main className="flex flex-1 items-center justify-center px-4 py-10">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex flex-col items-center gap-2 text-center">
            <div className="lg:hidden">
              <CompanyMark branding={branding} size="lg" showName={false} />
            </div>
            <h1 className="text-xl font-semibold text-text-primary">Sign in to {companyName}</h1>
            <p className="text-sm text-text-secondary lg:hidden">Procurement, inventory &amp; delivery management</p>
          </div>

          {notice && (
            <div role="status" className="mb-4 rounded-control bg-success-bg px-3 py-2 text-sm text-success-fg">
              {notice}
            </div>
          )}

          <BackendStatusNotice status={backend.status} elapsedMs={backend.elapsedMs} onRetry={backend.retry} />

          <form
            onSubmit={(event) => void handleSubmit(onSubmit)(event)}
            className="space-y-4 rounded-card border border-border bg-surface p-6 shadow-elev-1"
          >
            {formError && (
              <div role="alert" className="rounded-control bg-danger-bg px-3 py-2 text-sm text-danger-fg">
                {formError}
              </div>
            )}
            <div>
              <Label htmlFor="email" required>
                Email
              </Label>
              <Input
                id="email"
                type="email"
                autoComplete="username"
                error={errors.email?.message}
                {...register("email")}
              />
            </div>
            <div>
              <Label htmlFor="password" required>
                Password
              </Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                error={errors.password?.message}
                {...register("password")}
              />
            </div>
            <Button type="submit" className="w-full" disabled={isSubmitting || !isBackendReady}>
              {isSubmitting ? "Signing in…" : SUBMIT_LABELS[backend.status]}
            </Button>
            <p className="text-center text-sm">
              <Link to="/forgot-password" className="text-brand hover:underline">
                Forgot password?
              </Link>
            </p>
          </form>
        </div>
      </main>
    </div>
  );
}
