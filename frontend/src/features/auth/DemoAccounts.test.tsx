import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { type DemoAccount, useDemoAccounts } from "@/api/demo";
import { useAuth } from "@/lib/auth-context";

import { DemoAccounts } from "./DemoAccounts";

vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));
vi.mock("@/api/demo", () => ({ useDemoAccounts: vi.fn() }));

const accounts: DemoAccount[] = [
  {
    role: "admin",
    role_name: "admin",
    full_name: "Avery Quinn",
    email: "admin@demo.example.com",
    description: "Runs the company",
    is_portal: false,
  },
  {
    role: "supplier",
    role_name: "supplier",
    full_name: "Prairie Office Supply",
    email: "supplier@demo.example.com",
    description: "Supplier portal",
    is_portal: true,
  },
];

const demoLogin = vi.fn();

function renderPanel() {
  render(
    <MemoryRouter>
      <DemoAccounts enabled />
    </MemoryRouter>,
  );
}

describe("DemoAccounts", () => {
  beforeEach(() => {
    demoLogin.mockReset().mockResolvedValue(undefined);
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      isLoading: false,
      login: vi.fn(),
      demoLogin,
      logout: vi.fn(),
      hasPermission: () => false,
    });
    vi.mocked(useDemoAccounts).mockReturnValue({ data: accounts } as ReturnType<typeof useDemoAccounts>);
  });

  it("renders nothing when the server is not in demo mode", () => {
    vi.mocked(useDemoAccounts).mockReturnValue({ data: undefined } as ReturnType<typeof useDemoAccounts>);

    renderPanel();

    expect(screen.queryByRole("heading", { name: "Try the demo" })).not.toBeInTheDocument();
  });

  it("lists every demo role and marks the supplier portal", () => {
    renderPanel();

    expect(screen.getByRole("button", { name: /admin/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /supplier portal/i })).toBeInTheDocument();
  });

  it("signs in as the chosen role", async () => {
    renderPanel();

    fireEvent.click(screen.getByRole("button", { name: /admin/i }));

    await waitFor(() => expect(demoLogin).toHaveBeenCalledWith("admin"));
  });

  it("shows the server's reason when the demo sign-in fails", async () => {
    demoLogin.mockRejectedValue(new Error("Demo data has not been loaded"));
    renderPanel();

    fireEvent.click(screen.getByRole("button", { name: /admin/i }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
