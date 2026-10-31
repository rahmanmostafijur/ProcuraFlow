import { fireEvent, screen, waitFor } from "@testing-library/react";
import { AxiosError, type AxiosResponse } from "axios";
import { Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import { renderWithProviders } from "@/test/render";

import { AcceptInvitationPage } from "./AcceptInvitationPage";
import { ForgotPasswordPage } from "./ForgotPasswordPage";
import { ResetPasswordPage } from "./ResetPasswordPage";

function rejectWith(status: number, detail: string) {
  return new AxiosError("failed", "ERR_BAD_REQUEST", undefined, undefined, {
    status,
    data: { detail },
  } as AxiosResponse);
}

/** Stands in for the login page and shows the notice it was sent with. */
function LoginStub() {
  const notice = (useLocation().state as { notice?: string } | null)?.notice;
  return <p>Login page: {notice}</p>;
}

function renderRoutes(route: string) {
  renderWithProviders(
    <Routes>
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/accept-invitation" element={<AcceptInvitationPage />} />
      <Route path="/login" element={<LoginStub />} />
    </Routes>,
    { route },
  );
}

const fill = (label: string, value: string) =>
  fireEvent.change(screen.getByLabelText(new RegExp(`^${label}`)), { target: { value } });

describe("ForgotPasswordPage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("rejects an invalid email without calling the API", async () => {
    const post = vi.spyOn(apiClient, "post");
    renderRoutes("/forgot-password");

    fill("Email", "ada@example");
    fireEvent.click(screen.getByRole("button", { name: "Send reset link" }));

    expect(await screen.findByText("Enter a valid email address")).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();
  });

  it("shows the same neutral confirmation after sending", async () => {
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: { detail: "ok" } });
    renderRoutes("/forgot-password");

    fill("Email", "ada@example.com");
    fireEvent.click(screen.getByRole("button", { name: "Send reset link" }));

    expect(await screen.findByRole("status")).toHaveTextContent(/if an account exists/i);
    expect(post).toHaveBeenCalledWith("/auth/password-reset/request", { email: "ada@example.com" });
  });

  it("shows the server's message when the request fails", async () => {
    vi.spyOn(apiClient, "post").mockRejectedValue(rejectWith(429, "Too many requests"));
    renderRoutes("/forgot-password");

    fill("Email", "ada@example.com");
    fireEvent.click(screen.getByRole("button", { name: "Send reset link" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Too many requests");
  });
});

describe.each([
  {
    name: "ResetPasswordPage",
    path: "/reset-password",
    endpoint: "/auth/password-reset/confirm",
    button: "Reset password",
  },
  {
    name: "AcceptInvitationPage",
    path: "/accept-invitation",
    endpoint: "/auth/invitations/accept",
    button: "Activate account",
  },
])("$name", ({ path, endpoint, button }) => {
  afterEach(() => vi.restoreAllMocks());

  it("explains a link without a token and shows no form", () => {
    renderRoutes(path);

    expect(screen.getByRole("alert")).toHaveTextContent(/link is incomplete/i);
    expect(screen.queryByLabelText(/^New password/)).not.toBeInTheDocument();
  });

  it("requires at least 8 characters", async () => {
    const post = vi.spyOn(apiClient, "post");
    renderRoutes(`${path}?token=abc`);

    fill("New password", "short");
    fill("Confirm password", "short");
    fireEvent.click(screen.getByRole("button", { name: button }));

    expect(await screen.findByText("Password must be at least 8 characters")).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();
  });

  it("requires the confirmation to match", async () => {
    const post = vi.spyOn(apiClient, "post");
    renderRoutes(`${path}?token=abc`);

    fill("New password", "long-enough-1");
    fill("Confirm password", "long-enough-2");
    fireEvent.click(screen.getByRole("button", { name: button }));

    expect(await screen.findByText("Passwords do not match")).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();
  });

  it("sends the token and password, then goes to the login page with a notice", async () => {
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: undefined });
    renderRoutes(`${path}?token=abc`);

    fill("New password", "long-enough-1");
    fill("Confirm password", "long-enough-1");
    fireEvent.click(screen.getByRole("button", { name: button }));

    expect(await screen.findByText(/Login page: .*Sign in/)).toBeInTheDocument();
    expect(post).toHaveBeenCalledWith(endpoint, { token: "abc", password: "long-enough-1" });
  });

  it("shows the server's message for an invalid or expired link and stays on the page", async () => {
    vi.spyOn(apiClient, "post").mockRejectedValue(rejectWith(400, "This link is invalid or has expired."));
    renderRoutes(`${path}?token=stale`);

    fill("New password", "long-enough-1");
    fill("Confirm password", "long-enough-1");
    fireEvent.click(screen.getByRole("button", { name: button }));

    expect(await screen.findByRole("alert")).toHaveTextContent("This link is invalid or has expired.");
    await waitFor(() => expect(screen.getByRole("button", { name: button })).toBeEnabled());
    expect(screen.queryByText(/Login page/)).not.toBeInTheDocument();
  });
});
