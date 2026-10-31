import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

import { useChangePassword } from "@/api/auth";
import { extractErrorMessage } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { newPasswordSchema } from "@/features/auth/passwordSchema";
import { useAuth } from "@/lib/auth-context";

const schema = z
  .object({
    current_password: z.string().min(1, "Enter your current password"),
    new_password: newPasswordSchema,
    confirm: z.string().min(1, "Confirm your new password"),
  })
  .refine((values) => values.new_password === values.confirm, {
    message: "Passwords do not match",
    path: ["confirm"],
  });

type FormValues = z.infer<typeof schema>;

export function ProfilePage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const changePassword = useChangePassword();
  const [formError, setFormError] = useState<string | null>(null);
  const isChanged = useRef(false);
  const logoutRef = useRef(logout);
  useEffect(() => {
    logoutRef.current = logout;
  }, [logout]);

  // Signing out while this page is still routed would let ProtectedRoute redirect to /login without
  // the notice, so the sign-out waits until navigation has left this page.
  useEffect(
    () => () => {
      if (isChanged.current) logoutRef.current();
    },
    [],
  );

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    setFormError(null);
    try {
      await changePassword.mutateAsync({
        current_password: values.current_password,
        new_password: values.new_password,
      });
    } catch (error) {
      setFormError(extractErrorMessage(error));
      return;
    }
    // The server revokes every session on success, so this one is finished as well.
    isChanged.current = true;
    void navigate("/login", {
      replace: true,
      state: { notice: "Your password was changed. Sign in again with your new password." },
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Your profile</h1>
        <p className="text-sm text-slate-500">
          {user?.full_name} · {user?.email}
        </p>
      </div>

      <Card className="max-w-lg p-6">
        <h2 className="text-base font-semibold text-slate-900">Change password</h2>
        <p className="mb-4 text-sm text-slate-500">You will be signed out everywhere and asked to sign in again.</p>
        <form onSubmit={(event) => void handleSubmit(onSubmit)(event)} className="space-y-4">
          {formError && (
            <div role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
              {formError}
            </div>
          )}
          <div>
            <Label htmlFor="current_password" required>
              Current password
            </Label>
            <Input
              id="current_password"
              type="password"
              autoComplete="current-password"
              error={errors.current_password?.message}
              {...register("current_password")}
            />
          </div>
          <div>
            <Label htmlFor="new_password" required>
              New password
            </Label>
            <Input
              id="new_password"
              type="password"
              autoComplete="new-password"
              error={errors.new_password?.message}
              {...register("new_password")}
            />
          </div>
          <div>
            <Label htmlFor="confirm" required>
              Confirm new password
            </Label>
            <Input
              id="confirm"
              type="password"
              autoComplete="new-password"
              error={errors.confirm?.message}
              {...register("confirm")}
            />
          </div>
          <div className="flex justify-end">
            <Button type="submit" disabled={changePassword.isPending}>
              {changePassword.isPending ? "Saving…" : "Change password"}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
