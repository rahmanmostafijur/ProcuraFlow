import { createContext, useContext } from "react";

import type { User } from "@/api/types";

export interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  /** Demo mode only: signs in as one of the demo roles without a password. */
  demoLogin?: (role: string) => Promise<void>;
  logout: () => void;
  hasPermission: (code: string) => boolean;
}

// The provider lives in AuthProvider.tsx: a module that exports a component and anything else
// cannot be hot-reloaded by React Fast Refresh.
export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
