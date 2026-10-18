import axios from "axios";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from "react";

import { apiClient, hasSessionHint, setAccessToken, setSessionHint } from "@/api/client";
import type { User } from "@/api/types";

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  hasPermission: (code: string) => boolean;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchCurrentUser = useCallback(async () => {
    const { data } = await apiClient.get<User>("/auth/me");
    setUser(data);
  }, []);

  useEffect(() => {
    if (!hasSessionHint()) {
      setIsLoading(false);
      return;
    }

    // The refresh token rides in an httpOnly cookie, so a bare POST is enough to restore the session.
    apiClient
      .post("/auth/refresh")
      .then(async ({ data }) => {
        setAccessToken(data.access_token);
        await fetchCurrentUser();
      })
      .catch((error: unknown) => {
        // Only a 401 means the session is really gone; a sleeping or unreachable backend must not sign the user out.
        if (axios.isAxiosError(error) && error.response?.status === 401) {
          setSessionHint(false);
        }
      })
      .finally(() => setIsLoading(false));
  }, [fetchCurrentUser]);

  const login = useCallback(
    async (email: string, password: string) => {
      const { data } = await apiClient.post("/auth/login", { email, password });
      setAccessToken(data.access_token);
      setSessionHint(true);
      await fetchCurrentUser();
    },
    [fetchCurrentUser]
  );

  const logout = useCallback(() => {
    setAccessToken(null);
    setSessionHint(false);
    setUser(null);
    // Best effort: the user is signed out locally either way, and the cookie expires on its own.
    void apiClient.post("/auth/logout").catch(() => undefined);
  }, []);

  const hasPermission = useCallback(
    (code: string) => user?.role.permissions.some((permission) => permission.code === code) ?? false,
    [user]
  );

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout, hasPermission }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
