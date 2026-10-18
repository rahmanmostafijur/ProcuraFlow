import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAuth } from "@/lib/auth-context";
import { type BackendStatus, useBackendReadiness } from "@/lib/use-backend-readiness";

import { LoginPage } from "./LoginPage";

vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));
vi.mock("@/lib/use-backend-readiness", () => ({ useBackendReadiness: vi.fn() }));

const retry = vi.fn();

function renderLogin(status: BackendStatus, elapsedMs = 0) {
  vi.mocked(useBackendReadiness).mockReturnValue({ status, elapsedMs, retry });
  render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>
  );
}

const signInButton = () => screen.getByRole("button", { name: /sign in|connecting|waiting/i });

describe("LoginPage backend readiness", () => {
  beforeEach(() => {
    retry.mockReset();
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      hasPermission: () => false,
    });
  });

  it("enables sign in and shows no notice once the backend is ready", () => {
    renderLogin("ready");

    expect(signInButton()).toBeEnabled();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("holds sign in without any waking notice during the first moments of a check", () => {
    renderLogin("checking", 500);

    expect(signInButton()).toBeDisabled();
    expect(screen.queryByText(/waking the demo server/i)).not.toBeInTheDocument();
  });

  it("explains a cold start and shows progress against the budget while waking", () => {
    renderLogin("waking", 25_000);

    expect(screen.getByRole("status")).toHaveTextContent(/waking the demo server/i);
    expect(screen.getByRole("status")).toHaveTextContent("25s");
    const progress = screen.getByRole("progressbar");
    expect(progress).toHaveAttribute("aria-valuenow", "25");
    expect(signInButton()).toBeDisabled();
  });

  it("caps the progress readout at the budget", () => {
    renderLogin("waking", 250_000);

    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "100");
  });

  it("shows a clear error with a retry action when the backend never answers, never a spinner", () => {
    renderLogin("unavailable", 100_000);

    expect(screen.getByRole("alert")).toHaveTextContent(/couldn.t reach the server/i);
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(signInButton()).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: /try again/i }));

    expect(retry).toHaveBeenCalledTimes(1);
  });
});
