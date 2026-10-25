import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockGet, renderWithProviders } from "@/test/render";

import { Sidebar } from "./Sidebar";

const settings = { company_name: "Northbeam", brand_color: "#0F766E", logo_url: null };

function serve(total: number) {
  return mockGet({ "/company-settings": settings, "/approvals/queue": { items: [], total } });
}

describe("Sidebar", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows how many approvals are waiting, equal to the queue total", async () => {
    serve(3);
    renderWithProviders(<Sidebar />);

    expect(await screen.findByLabelText("3 waiting for you")).toHaveTextContent("3");
  });

  it("asks the queue for a single item, since only the total is needed", async () => {
    const get = serve(2);
    renderWithProviders(<Sidebar />);

    await screen.findByLabelText("2 waiting for you");
    expect(get).toHaveBeenCalledWith("/approvals/queue", { params: { page: 1, page_size: 1 } });
  });

  it("hides the badge when nothing is waiting", async () => {
    const get = serve(0);
    renderWithProviders(<Sidebar />);

    await waitFor(() => expect(get).toHaveBeenCalledWith("/approvals/queue", expect.anything()));
    expect(screen.getByRole("link", { name: /Approvals/ })).toBeInTheDocument();
    expect(screen.queryByLabelText(/waiting for you/)).not.toBeInTheDocument();
  });

  it("shows the new pages only to people who may use them", () => {
    serve(0);
    renderWithProviders(<Sidebar />);

    expect(screen.getByRole("link", { name: "Approvals" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Catalog" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Requests" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Budgets" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Approval settings" })).not.toBeInTheDocument();
  });

  it("shows Requests for an approver, Budgets for a reader and settings for an approval manager", () => {
    serve(0);
    renderWithProviders(<Sidebar />, { permissions: ["request:approve", "budget:read", "approval:manage"] });

    expect(screen.getByRole("link", { name: "Requests" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Budgets" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Approval settings" })).toBeInTheDocument();
  });
});
