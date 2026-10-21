import axios from "axios";
import { type ReactNode, useCallback, useEffect, useState } from "react";

import { apiClient, hasSessionHint, setAccessToken, setSessionHint } from "@/api/client";
import type { AccessTokenResponse, User } from "@/api/types";

import { AuthContext } from "./auth-context";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  // Without a session hint there is nothing to restore, so the app is ready from the first render.
  const [isLoading, setIsLoading] = useState(hasSessionHint);

  const fetchCurrentUser = useCallback(async () => {
    const { data } = await apiClient.get<User>("/auth/me");
    setUser(data);
  }, []);

  useEffect(() => {
    if (!hasSessionHint()) return;

    // The refresh token rides in an httpOnly cookie, so a bare POST is enough to restore the session.
    apiClient
      .post<AccessTokenResponse>("/auth/refresh")
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
      const { data } = await apiClient.post<AccessTokenResponse>("/auth/login", { email, password });
      setAccessToken(data.access_token);
      setSessionHint(true);
      await fetchCurrentUser();
    },
    [fetchCurrentUser],
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
    [user],
  );

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout, hasPermission }}>{children}</AuthContext.Provider>
  );
}
