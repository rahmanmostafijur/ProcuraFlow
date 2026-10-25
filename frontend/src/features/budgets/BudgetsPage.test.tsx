import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import type { BudgetPosition, BudgetTransfer } from "@/api/types";
import { person } from "@/test/fixtures";
import { mockGet, renderWithProviders } from "@/test/render";

import { BudgetsPage } from "./BudgetsPage";

function position(overrides: Partial<BudgetPosition>): BudgetPosition {
  return {
    budget_id: 1,
    cost_centre_id: 4,
    cost_centre_code: "IT",
    cost_centre_name: "Information Technology",
    fiscal_year: 2026,
    budget: "10000.00",
    spent: "1000.00",
    committed: "500.00",
    remaining: "8500.00",
    utilisation_percent: "15.00",
    health: "ok",
    ...overrides,
  };
}

const positions = [
  position({}),
  position({
    budget_id: 2,
    cost_centre_code: "OPS",
    cost_centre_name: "Operations",
    health: "warning",
    utilisation_percent: "92.50",
  }),
  position({
    budget_id: 3,
    cost_centre_code: "HR",
    cost_centre_name: "People",
    health: "over",
    remaining: "-200.00",
    utilisation_percent: "102.00",
  }),
];

const transfer: BudgetTransfer = {
  id: 6,
  from_budget_id: 1,
  to_budget_id: 3,
  from_label: "IT 2026",
  to_label: "HR 2026",
  amount: "750.00",
  reason: "Cover hiring",
  status: "pending",
  requested_by: person(2, "Rita Requester"),
  decided_by: null,
  decided_at: null,
  decision_comment: null,
  created_at: "2026-10-20T09:00:00Z",
};

function serve() {
  return mockGet({
    "/budgets": positions,
    "/budget-transfers": [transfer],
    "/cost-centres": [{ id: 4, code: "IT", name: "Information Technology", manager_id: null, is_active: true }],
    "/budgets/1/history": [
      {
        id: 1,
        change_type: "created",
        old_amount: null,
        new_amount: "10000.00",
        reason: "Annual plan",
        transfer_id: null,
        changed_by: 1,
        created_at: "2026-01-02T00:00:00Z",
      },
    ],
  });
}

describe("BudgetsPage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows each position with its health badge", async () => {
    serve();
    renderWithProviders(<BudgetsPage />, { permissions: ["budget:read"] });

    const ok = (await screen.findByText("IT — Information Technology")).closest("tr") as HTMLElement;
    expect(within(ok).getByText("On track")).toBeInTheDocument();
    expect(within(ok).getByText("$10,000.00")).toBeInTheDocument();
    expect(within(ok).getByText("15.0%")).toBeInTheDocument();
    expect(
      within(screen.getByText("OPS — Operations").closest("tr") as HTMLElement).getByText("Nearly used"),
    ).toBeInTheDocument();
    const over = screen.getByText("HR — People").closest("tr") as HTMLElement;
    expect(within(over).getByText("Over budget")).toBeInTheDocument();
    expect(within(over).getByText("-$200.00")).toBeInTheDocument();
  });

  it("hides every management control from someone who can only read", async () => {
    serve();
    renderWithProviders(<BudgetsPage />, { permissions: ["budget:read"] });
    await screen.findByText("IT — Information Technology");

    expect(screen.queryByText("Set a budget")).not.toBeInTheDocument();
    expect(screen.queryByText("Cost centres")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Request transfer" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve transfer 6" })).not.toBeInTheDocument();
    expect(await screen.findByText("Cover hiring")).toBeInTheDocument();
  });

  it("lets a department manager request a transfer but not decide one", async () => {
    serve();
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: transfer });
    renderWithProviders(<BudgetsPage />, { permissions: ["budget:read", "budget:request_transfer"] });
    await screen.findByText("IT — Information Technology");

    expect(screen.queryByRole("button", { name: "Approve transfer 6" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Request transfer" }));
    expect(await screen.findByText("Choose where the money comes from")).toBeInTheDocument();
    expect(screen.getByText("Say why the money is moving")).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Move from"), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText("Move to"), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText("Transfer amount"), { target: { value: "250.50" } });
    fireEvent.change(screen.getByLabelText("Reason for transfer"), { target: { value: "Cover hiring" } });
    fireEvent.click(screen.getByRole("button", { name: "Request transfer" }));
    expect(await screen.findByText("Choose a different budget")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Move to"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Request transfer" }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/budget-transfers", {
        from_budget_id: 1,
        to_budget_id: 3,
        amount: "250.50",
        reason: "Cover hiring",
      }),
    );
  });

  it("lets finance set a budget with the amount as typed", async () => {
    serve();
    const put = vi.spyOn(apiClient, "put").mockResolvedValue({ data: positions[0] });
    renderWithProviders(<BudgetsPage />, { permissions: ["budget:read", "budget:manage"] });
    await screen.findAllByRole("option", { name: "IT — Information Technology" });

    fireEvent.change(screen.getByLabelText("Cost centre to budget"), { target: { value: "4" } });
    fireEvent.change(screen.getByLabelText("Budget amount"), { target: { value: "12500" } });
    fireEvent.click(screen.getByRole("button", { name: "Save budget" }));

    await waitFor(() =>
      expect(put).toHaveBeenCalledWith("/budgets", {
        cost_centre_id: 4,
        fiscal_year: 2026,
        amount: "12500",
        reason: undefined,
      }),
    );
  });

  it("needs a reason to reject a transfer", async () => {
    serve();
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: transfer });
    renderWithProviders(<BudgetsPage />, { permissions: ["budget:read", "budget:manage"] });

    fireEvent.click(await screen.findByRole("button", { name: "Reject transfer 6" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(dialog.querySelector("button[type=submit]") as HTMLElement);
    expect(await screen.findByText("A comment is required to reject")).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText(/Reason for rejecting/), { target: { value: "Not now" } });
    fireEvent.click(dialog.querySelector("button[type=submit]") as HTMLElement);

    await waitFor(() => expect(post).toHaveBeenCalledWith("/budget-transfers/6/reject", { comment: "Not now" }));
  });

  it("opens the history of a budget", async () => {
    serve();
    renderWithProviders(<BudgetsPage />, { permissions: ["budget:read"] });

    fireEvent.click(await screen.findByRole("button", { name: "History of IT" }));

    expect(await screen.findByText("Annual plan")).toBeInTheDocument();
    expect(screen.getByText("Budget set")).toBeInTheDocument();
  });
});
