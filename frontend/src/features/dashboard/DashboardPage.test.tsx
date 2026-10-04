import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import type { DashboardSummary, RecentActivityItem } from "@/api/types";
import { useAuth } from "@/lib/auth-context";

import { DashboardPage } from "./DashboardPage";

vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));

const RECENT_ACTIVITY_URL = "/dashboard/recent-activity";

const summary: DashboardSummary = {
  total_purchase_orders: 3,
  pending_orders: 1,
  completed_orders: 1,
  supplier_count: 2,
  inventory_value: "100.00",
  low_stock_products: 0,
  upcoming_deliveries: 0,
};

const activity: RecentActivityItem[] = [
  {
    id: 1,
    action: "supplier_created",
    entity_type: "supplier",
    entity_id: 7,
    created_at: "2026-10-01T12:00:00Z",
    user_name: "Ada Admin",
  },
];

const responses: Record<string, unknown> = {
  "/dashboard/summary": summary,
  "/dashboard/monthly-trends": [],
  [RECENT_ACTIVITY_URL]: activity,
};

function signInWith(...codes: string[]) {
  vi.mocked(useAuth).mockReturnValue({
    user: null,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
    hasPermission: (code: string) => codes.includes(code),
  });
}

function renderDashboard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <DashboardPage />
    </QueryClientProvider>
  );
}

function requestedUrls(): unknown[] {
  return vi.mocked(apiClient.get).mock.calls.map(([url]) => url);
}

describe("DashboardPage activity feed", () => {
  beforeEach(() => {
    vi.spyOn(apiClient, "get").mockImplementation(async (url: string) => ({ data: responses[url] }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows recent activity to users who can read the audit log", async () => {
    signInWith("audit:read");

    renderDashboard();

    expect(await screen.findByText("Recent Activity")).toBeInTheDocument();
    expect(await screen.findByText("Ada Admin")).toBeInTheDocument();
    expect(requestedUrls()).toContain(RECENT_ACTIVITY_URL);
  });

  it("neither requests nor renders recent activity without audit:read", async () => {
    signInWith("po:create");

    renderDashboard();

    expect(await screen.findByText("Committed Spend by Month")).toBeInTheDocument();
    expect(screen.queryByText("Recent Activity")).not.toBeInTheDocument();
    expect(requestedUrls()).not.toContain(RECENT_ACTIVITY_URL);
  });
});
