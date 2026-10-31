import { useConfirmPasswordReset } from "@/api/auth";

import { SetPasswordPage } from "./SetPasswordPage";

export function ResetPasswordPage() {
  const confirmReset = useConfirmPasswordReset();

  return (
    <SetPasswordPage
      title="Choose a new password"
      description="Pick a password you have not used here before."
      submitLabel="Reset password"
      missingTokenMessage="This password reset link is incomplete. Request a new one from the sign-in page."
      successNotice="Your password was reset. Sign in with your new password."
      submit={(token, password) => confirmReset.mutateAsync({ token, password })}
    />
  );
}
