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
    return <Navigate to="/" replace />;
  }

  const onSubmit = async (values: LoginFormValues) => {
    setFormError(null);
    try {
      await login(values.email, values.password);
      void navigate("/");
    } catch (error) {
      setFormError(extractErrorMessage(error));
    }
  };

  const isBackendReady = backend.status === "ready";

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-2">
          <CompanyMark branding={branding} size="lg" showName={false} />
          <h1 className="text-xl font-semibold text-slate-900">Sign in to {companyName}</h1>
          <p className="text-sm text-slate-500">Procurement, inventory &amp; delivery management</p>
        </div>

        {notice && (
          <div role="status" className="mb-4 rounded-md bg-green-50 px-3 py-2 text-sm text-green-800">
            {notice}
          </div>
        )}

        <BackendStatusNotice status={backend.status} elapsedMs={backend.elapsedMs} onRetry={backend.retry} />

        <form
          onSubmit={(event) => void handleSubmit(onSubmit)(event)}
          className="space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm"
        >
          {formError && (
            <div role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
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
            <Link to="/forgot-password" className="text-brand-600 hover:underline">
              Forgot password?
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
