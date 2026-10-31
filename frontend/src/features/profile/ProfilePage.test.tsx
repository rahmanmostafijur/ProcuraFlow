import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { AxiosError, type AxiosResponse } from "axios";
import { useState } from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import type { User } from "@/api/types";
import { AuthContext } from "@/lib/auth-context";
import { ProtectedRoute } from "@/routes/ProtectedRoute";
import { testUser } from "@/test/render";

import { ProfilePage } from "./ProfilePage";

function LoginStub() {
  const notice = (useLocation().state as { notice?: string } | null)?.notice;
  return <p>Login page: {notice}</p>;
}

/** A real sign-out: the user disappears from context, so ProtectedRoute reacts exactly as in the app. */
function Harness() {
  const [user, setUser] = useState<User | null>(testUser);
  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading: false,
        login: () => Promise.resolve(),
        logout: () => setUser(null),
        hasPermission: () => false,
      }}
    >
      <Routes>
        <Route path="/login" element={<LoginStub />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/profile" element={<ProfilePage />} />
        </Route>
      </Routes>
    </AuthContext.Provider>
  );
}

function renderProfile() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/profile"]}>
        <Harness />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const fill = (label: string, value: string) =>
  fireEvent.change(screen.getByLabelText(new RegExp(`^${label}`)), { target: { value } });

function submitPasswords(current: string, next: string, confirm = next) {
  fill("Current password", current);
  fill("New password", next);
  fill("Confirm new password", confirm);
  fireEvent.click(screen.getByRole("button", { name: "Change password" }));
}

describe("ProfilePage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("signs the user out and shows a notice on the login page after a successful change", async () => {
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: undefined });
    renderProfile();

    submitPasswords("old-password", "brand-new-pass");

    expect(await screen.findByText(/Login page: Your password was changed/)).toBeInTheDocument();
    expect(post).toHaveBeenCalledWith("/auth/change-password", {
      current_password: "old-password",
      new_password: "brand-new-pass",
    });
  });

  it("keeps the user signed in and shows the server's message when the current password is wrong", async () => {
    vi.spyOn(apiClient, "post").mockRejectedValue(
      new AxiosError("bad", "ERR_BAD_REQUEST", undefined, undefined, {
        status: 400,
        data: { detail: "Current password is incorrect" },
      } as AxiosResponse),
    );
    renderProfile();

    submitPasswords("wrong", "brand-new-pass");

    expect(await screen.findByRole("alert")).toHaveTextContent("Current password is incorrect");
    expect(screen.queryByText(/Login page/)).not.toBeInTheDocument();
  });

  it("rejects a mismatched confirmation without calling the API", async () => {
    const post = vi.spyOn(apiClient, "post");
    renderProfile();

    submitPasswords("old-password", "brand-new-pass", "different-pass");

    expect(await screen.findByText("Passwords do not match")).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();
  });
});
