import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { extractErrorMessage } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";

import { AuthPageLayout } from "./AuthPageLayout";
import { type SetPasswordValues, setPasswordSchema } from "./passwordSchema";

interface SetPasswordPageProps {
  title: string;
  description: string;
  submitLabel: string;
  missingTokenMessage: string;
  successNotice: string;
  submit: (token: string, password: string) => Promise<unknown>;
}

/** Reads `?token=` from the link and asks for a new password; the reset and invitation pages differ only in copy and endpoint. */
export function SetPasswordPage({
  title,
  description,
  submitLabel,
  missingTokenMessage,
  successNotice,
  submit,
}: SetPasswordPageProps) {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token");
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<SetPasswordValues>({ resolver: zodResolver(setPasswordSchema) });

  if (!token) {
    return (
      <AuthPageLayout title={title}>
        <div role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {missingTokenMessage}
        </div>
        <p className="mt-4 text-center text-sm">
          <Link to="/login" className="text-brand-600 hover:underline">
            Back to sign in
          </Link>
        </p>
      </AuthPageLayout>
    );
  }

  const onSubmit = async (values: SetPasswordValues) => {
    setFormError(null);
    try {
      await submit(token, values.password);
      void navigate("/login", { replace: true, state: { notice: successNotice } });
    } catch (error) {
      setFormError(extractErrorMessage(error));
    }
  };

  return (
    <AuthPageLayout title={title} description={description}>
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
          <Label htmlFor="password" required>
            New password
          </Label>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            error={errors.password?.message}
            {...register("password")}
          />
        </div>
        <div>
          <Label htmlFor="confirm" required>
            Confirm password
          </Label>
          <Input
            id="confirm"
            type="password"
            autoComplete="new-password"
            error={errors.confirm?.message}
            {...register("confirm")}
          />
        </div>
        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? "Saving…" : submitLabel}
        </Button>
      </form>
    </AuthPageLayout>
  );
}
