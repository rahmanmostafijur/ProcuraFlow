import { useAcceptInvitation } from "@/api/auth";

import { SetPasswordPage } from "./SetPasswordPage";

export function AcceptInvitationPage() {
  const acceptInvitation = useAcceptInvitation();

  return (
    <SetPasswordPage
      title="Accept your invitation"
      description="Choose a password to finish setting up your account."
      submitLabel="Activate account"
      missingTokenMessage="This invitation link is incomplete. Ask your administrator to send a new invitation."
      successNotice="Your account is ready. Sign in with your new password."
      submit={(token, password) => acceptInvitation.mutateAsync({ token, password })}
    />
  );
}
