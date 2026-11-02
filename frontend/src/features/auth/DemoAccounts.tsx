import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { extractErrorMessage } from "@/api/client";
import { type DemoAccount, useDemoAccounts } from "@/api/demo";
import { useAuth } from "@/lib/auth-context";

interface DemoAccountsProps {
  /** Wait for the backend to answer before asking, so a sleeping server does not show an error. */
  enabled: boolean;
}

/** One-click sign-in for each demo role. Renders nothing unless the server runs in demo mode. */
export function DemoAccounts({ enabled }: DemoAccountsProps) {
  const { demoLogin } = useAuth();
  const navigate = useNavigate();
  const { data: accounts } = useDemoAccounts(enabled);
  const [pendingRole, setPendingRole] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!demoLogin || !accounts || accounts.length === 0) return null;

  const signIn = async (account: DemoAccount) => {
    setError(null);
    setPendingRole(account.role);
    try {
      await demoLogin(account.role);
      // The landing page at "/" sends the signed-in user to the right home.
      void navigate("/");
    } catch (failure) {
      setError(extractErrorMessage(failure));
      setPendingRole(null);
    }
  };

  return (
    <section aria-labelledby="demo-heading" className="mt-6 rounded-card border border-border bg-surface p-6">
      <h2 id="demo-heading" className="text-title text-text-primary">
        Try the demo
      </h2>
      <p className="mt-1 text-sm text-text-secondary">Pick a role to sign in with sample data. No password needed.</p>
      {error && (
        <p role="alert" className="mt-3 rounded-control bg-danger-bg px-3 py-2 text-sm text-danger-fg">
          {error}
        </p>
      )}
      <ul className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
        {accounts.map((account) => (
          <li key={account.role}>
            <button
              type="button"
              disabled={pendingRole !== null}
              onClick={() => void signIn(account)}
              className="w-full rounded-control border border-border bg-bg px-3 py-2 text-left transition-colors duration-fast hover:border-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:cursor-not-allowed disabled:opacity-60"
            >
              <span className="block text-sm font-medium capitalize text-text-primary">
                {pendingRole === account.role ? "Signing in…" : account.role_name.replace(/_/g, " ")}
              </span>
              <span className="block truncate text-xs text-text-secondary">
                {account.full_name}
                {account.is_portal ? " · supplier portal" : ""}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
