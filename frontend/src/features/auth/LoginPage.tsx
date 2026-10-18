import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useNavigate } from "react-router-dom";
import { z } from "zod";

import { extractErrorMessage } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { useAuth } from "@/lib/auth-context";
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
  const [formError, setFormError] = useState<string | null>(null);
  const backend = useBackendReadiness();

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
      navigate("/");
    } catch (error) {
      setFormError(extractErrorMessage(error));
    }
  };

  const isBackendReady = backend.status === "ready";

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-2">
          <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-brand-600 text-lg font-bold text-white">
            PF
          </div>
          <h1 className="text-xl font-semibold text-slate-900">Sign in to ProcuraFlow</h1>
          <p className="text-sm text-slate-500">Procurement, inventory &amp; delivery management</p>
        </div>

        <BackendStatusNotice status={backend.status} elapsedMs={backend.elapsedMs} onRetry={backend.retry} />

        <form
          onSubmit={handleSubmit(onSubmit)}
          className="space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm"
        >
          {formError && <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{formError}</div>}
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
        </form>
      </div>
    </div>
  );
}
