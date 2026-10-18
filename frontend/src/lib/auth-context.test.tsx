import { act, render, screen, waitFor } from "@testing-library/react";
import { AxiosError, type AxiosResponse } from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient, hasSessionHint, setSessionHint } from "@/api/client";
import type { User } from "@/api/types";

import { AuthProvider, useAuth } from "./auth-context";

const adminUser = {
  id: 1,
  email: "admin@example.com",
  full_name: "Ada Admin",
  role: { name: "admin", permissions: [] },
} as unknown as User;

function Probe() {
  const { user, isLoading, login, logout } = useAuth();
  return (
    <div>
      <span data-testid="state">{isLoading ? "loading" : (user?.email ?? "anonymous")}</span>
      <button onClick={() => void login("admin@example.com", "pw")}>login</button>
      <button onClick={logout}>logout</button>
    </div>
  );
}

function renderProvider() {
  render(
    <AuthProvider>
      <Probe />
    </AuthProvider>
  );
}

const ok = <T,>(data: T) => Promise.resolve({ data } as AxiosResponse<T>);
const failWith = (status?: number) =>
  Promise.reject(
    new AxiosError("failed", undefined, undefined, undefined, status ? ({ status } as AxiosResponse) : undefined)
  );

describe("AuthProvider cookie session", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("skips the refresh call entirely for a visitor without a session hint", async () => {
    const post = vi.spyOn(apiClient, "post");
    renderProvider();

    await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("anonymous"));
    expect(post).not.toHaveBeenCalled();
  });

  it("restores the session from the cookie with a bodiless refresh", async () => {
    setSessionHint(true);
    const post = vi.spyOn(apiClient, "post").mockReturnValue(ok({ access_token: "a" }));
    vi.spyOn(apiClient, "get").mockReturnValue(ok(adminUser));

    renderProvider();

    await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("admin@example.com"));
    expect(post).toHaveBeenCalledWith("/auth/refresh");
  });

  it("forgets the hint when the server says the session is over", async () => {
    setSessionHint(true);
    vi.spyOn(apiClient, "post").mockImplementation(() => failWith(401));

    renderProvider();

    await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("anonymous"));
    expect(hasSessionHint()).toBe(false);
  });

  it("keeps the hint when the backend is merely unreachable", async () => {
    setSessionHint(true);
    vi.spyOn(apiClient, "post").mockImplementation(() => failWith());

    renderProvider();

    await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("anonymous"));
    expect(hasSessionHint()).toBe(true);
  });

  it("stores only the non-secret hint on login, never a token", async () => {
    vi.spyOn(apiClient, "post").mockReturnValue(ok({ access_token: "secret-access-token" }));
    vi.spyOn(apiClient, "get").mockReturnValue(ok(adminUser));
    renderProvider();
    await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("anonymous"));

    await act(async () => screen.getByText("login").click());

    await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("admin@example.com"));
    expect(Object.fromEntries(Object.entries(localStorage))).toEqual({ procuraflow_has_session: "1" });
  });

  it("clears the hint and asks the server to drop the cookie on logout", async () => {
    setSessionHint(true);
    const post = vi.spyOn(apiClient, "post").mockImplementation((url: string) =>
      url === "/auth/refresh" ? ok({ access_token: "a" }) : ok(undefined)
    );
    vi.spyOn(apiClient, "get").mockReturnValue(ok(adminUser));
    renderProvider();
    await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("admin@example.com"));

    await act(async () => screen.getByText("logout").click());

    expect(screen.getByTestId("state")).toHaveTextContent("anonymous");
    expect(hasSessionHint()).toBe(false);
    expect(post).toHaveBeenCalledWith("/auth/logout");
  });
});
