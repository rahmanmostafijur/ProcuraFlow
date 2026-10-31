import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";

import { useRequestPasswordReset } from "@/api/auth";
import { extractErrorMessage } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";

import { AuthPageLayout } from "./AuthPageLayout";

const forgotSchema = z.object({ email: z.string().email("Enter a valid email address") });

type ForgotFormValues = z.infer<typeof forgotSchema>;

export function ForgotPasswordPage() {
  const requestReset = useRequestPasswordReset();
  const [isSent, setSent] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ForgotFormValues>({ resolver: zodResolver(forgotSchema) });

  const onSubmit = async (values: ForgotFormValues) => {
    setFormError(null);
    try {
      await requestReset.mutateAsync(values.email);
      setSent(true);
    } catch (error) {
      setFormError(extractErrorMessage(error));
    }
  };

  const backLink = (
    <p className="mt-4 text-center text-sm">
      <Link to="/login" className="text-brand-600 hover:underline">
        Back to sign in
      </Link>
    </p>
  );

  if (isSent) {
    return (
      <AuthPageLayout title="Check your email">
        <div role="status" className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-800">
          If an account exists for that address, we have sent a link to reset the password. It expires soon, so use it
          promptly.
        </div>
        {backLink}
      </AuthPageLayout>
    );
  }

  return (
    <AuthPageLayout title="Forgot your password?" description="Enter your email and we will send you a reset link.">
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
          <Input id="email" type="email" autoComplete="username" error={errors.email?.message} {...register("email")} />
        </div>
        <Button type="submit" className="w-full" disabled={requestReset.isPending}>
          {requestReset.isPending ? "Sending…" : "Send reset link"}
        </Button>
      </form>
      {backLink}
    </AuthPageLayout>
  );
}
