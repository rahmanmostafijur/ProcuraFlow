import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from "react";

import { apiClient, getRefreshToken, setAccessToken, setRefreshToken } from "@/api/client";
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
    const refreshToken = getRefreshToken();
    if (!refreshToken) {
      setIsLoading(false);
      return;
    }

    apiClient
      .post("/auth/refresh", { refresh_token: refreshToken })
      .then(async ({ data }) => {
        setAccessToken(data.access_token);
        await fetchCurrentUser();
      })
      .catch(() => {
        setRefreshToken(null);
      })
      .finally(() => setIsLoading(false));
  }, [fetchCurrentUser]);

  const login = useCallback(
    async (email: string, password: string) => {
      const { data } = await apiClient.post("/auth/login", { email, password });
      setAccessToken(data.access_token);
      setRefreshToken(data.refresh_token);
      await fetchCurrentUser();
    },
    [fetchCurrentUser]
  );

  const logout = useCallback(() => {
    setAccessToken(null);
    setRefreshToken(null);
    setUser(null);
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
