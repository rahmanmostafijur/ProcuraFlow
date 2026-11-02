import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { App } from "@/App";
import { apiClient } from "@/api/client";
import { ThemeProvider } from "@/lib/theme";
import { AuthContext } from "@/lib/auth-context";
import { renderWithProviders, testUser } from "@/test/render";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { LandingPage } from "./LandingPage";

function renderAnonymousApp() {
  return render(
    <AuthContext.Provider
      value={{
        user: null,
        isLoading: false,
        login: () => Promise.resolve(),
        logout: () => undefined,
        hasPermission: () => false,
      }}
    >
      <ThemeProvider>
        <MemoryRouter initialEntries={["/"]}>
          <App />
        </MemoryRouter>
      </ThemeProvider>
    </AuthContext.Provider>,
  );
}

describe("landing page", () => {
  it("renders exactly one h1 and a sign-in link", () => {
    renderWithProviders(
      <ThemeProvider>
        <LandingPage />
      </ThemeProvider>,
    );

    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getAllByRole("link", { name: "Sign in" })[0]).toHaveAttribute("href", "/login");
    expect(screen.getAllByRole("link", { name: /demo/i })[0]).toHaveAttribute("href", "/login?demo=1");
    expect(document.title).toContain("ProcuraFlow");
  });

  it("shows the landing page to an anonymous visitor at /", async () => {
    renderAnonymousApp();
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("No monthly fee");
  });

  it("sends a signed-in internal user at / to the dashboard route", async () => {
    const branding = { company_name: "Northbeam", brand_color: "#0F766E", logo_url: null };
    vi.spyOn(apiClient, "get").mockImplementation((url) => {
      if (url === "/company-settings/branding") return Promise.resolve({ data: branding });
      if (url === "/company-settings")
        return Promise.resolve({ data: { ...branding, updated_at: "2026-11-01T00:00:00Z" } });
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });
    renderWithProviders(
      <ThemeProvider>
        <App />
      </ThemeProvider>,
      { user: testUser, route: "/" },
    );

    expect(await screen.findByRole("link", { name: "Dashboard" })).toHaveAttribute("aria-current", "page");
    expect(screen.queryByRole("heading", { level: 1, name: /No monthly fee/ })).not.toBeInTheDocument();
    vi.restoreAllMocks();
  });

  it("opens and closes a FAQ answer", () => {
    renderWithProviders(
      <ThemeProvider>
        <LandingPage />
      </ThemeProvider>,
    );

    const question = screen.getByRole("button", { name: "Is there a monthly fee?" });
    expect(question).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(question);
    expect(question).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("region", { name: "Is there a monthly fee?" })).toBeVisible();
    fireEvent.click(question);
    expect(question).toHaveAttribute("aria-expanded", "false");
  });
});
