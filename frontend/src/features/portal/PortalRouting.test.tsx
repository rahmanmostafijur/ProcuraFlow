import { screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/App";
import { apiClient } from "@/api/client";
import type { User } from "@/api/types";
import { ThemeProvider } from "@/lib/theme";
import { renderWithProviders, testUser } from "@/test/render";

const supplierUser: User = {
  ...testUser,
  id: 20,
  full_name: "Sam Supplier",
  supplier_id: 3,
  role: { id: 9, name: "supplier", description: null, permissions: [] },
};

const page = { items: [], total: 0, page: 1, page_size: 10, total_pages: 0 };
const branding = { company_name: "Northbeam", brand_color: "#0F766E", logo_url: null };

describe("routing between the internal app and the supplier portal", () => {
  let requested: string[];

  beforeEach(() => {
    requested = [];
    vi.spyOn(apiClient, "get").mockImplementation((url) => {
      requested.push(url);
      if (url === "/company-settings/branding") return Promise.resolve({ data: branding });
      if (url === "/company-settings")
        return Promise.resolve({ data: { ...branding, updated_at: "2026-11-01T00:00:00Z" } });
      if (url === "/portal/orders") return Promise.resolve({ data: page });
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });
  });

  afterEach(() => vi.restoreAllMocks());

  it("sends a supplier who lands on the home page to the portal shell", async () => {
    renderWithProviders(
      <ThemeProvider>
        <App />
      </ThemeProvider>,
      { user: supplierUser, route: "/" },
    );

    expect(await screen.findByRole("heading", { name: "Your orders" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Supplier portal" })).toBeInTheDocument();
    for (const label of ["Orders", "Invoices", "Documents", "Password"]) {
      expect(screen.getByRole("link", { name: label })).toBeInTheDocument();
    }
    expect(screen.queryByRole("link", { name: "Purchase Orders" })).not.toBeInTheDocument();
  });

  it("never renders or calls the internal app for a supplier, whichever internal URL they open", async () => {
    renderWithProviders(
      <ThemeProvider>
        <App />
      </ThemeProvider>,
      { user: supplierUser, route: "/suppliers" },
    );

    expect(await screen.findByRole("heading", { name: "Your orders" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Suppliers" })).not.toBeInTheDocument();
    expect(requested.filter((url) => !url.startsWith("/portal") && !url.includes("branding"))).toEqual([]);
  });

  it("sends an internal user who opens /portal back to the dashboard", async () => {
    renderWithProviders(
      <ThemeProvider>
        <App />
      </ThemeProvider>,
      { user: testUser, route: "/portal" },
    );

    // The internal sidebar renders and the dashboard is the current page.
    expect(await screen.findByRole("link", { name: "Dashboard" })).toHaveAttribute("aria-current", "page");
    expect(screen.queryByRole("navigation", { name: "Supplier portal" })).not.toBeInTheDocument();
  });
});
