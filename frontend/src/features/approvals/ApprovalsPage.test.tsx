import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import type { Delegation } from "@/api/types";
import { queueItem, person } from "@/test/fixtures";
import { mockGet, renderWithProviders } from "@/test/render";

import { ApprovalsPage } from "./ApprovalsPage";

const delegation: Delegation = {
  id: 3,
  delegator: person(1, "Me Myself"),
  delegate: person(8, "Dana Deputy"),
  starts_on: "2099-01-01",
  ends_on: "2099-01-10",
  revoked_at: null,
  created_at: "2026-10-01T00:00:00Z",
};

function serve(items = [queueItem()], delegations: Delegation[] = []) {
  return mockGet({
    "/approvals/queue": { items, total: items.length },
    "/approval-delegations": delegations,
  });
}

describe("ApprovalsPage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("lists what is waiting with amount, step and a link to the document", async () => {
    serve([
      queueItem(),
      queueItem({ document_type: "purchase_order", document_id: 7, label: "PO-0007", title: "Cables" }),
    ]);
    renderWithProviders(<ApprovalsPage />);

    const row = (await screen.findByText("Laptops for new hires")).closest("tr") as HTMLElement;
    expect(within(row).getByRole("link", { name: "REQ-0005" })).toHaveAttribute("href", "/requests/5");
    expect(within(row).getByText("$4,800.00")).toBeInTheDocument();
    expect(within(row).getByText("2 of 3")).toBeInTheDocument();
    const orderRow = screen.getByText("Cables").closest("tr") as HTMLElement;
    expect(within(orderRow).getByRole("link", { name: "PO-0007" })).toHaveAttribute("href", "/purchase-orders/7");
  });

  it("approves with an optional comment", async () => {
    serve();
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: {} });
    renderWithProviders(<ApprovalsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Approve REQ-0005" }));
    fireEvent.change(screen.getByLabelText("Comment (optional)"), { target: { value: "Looks fine" } });
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() => expect(post).toHaveBeenCalledWith("/purchase-requests/5/approve", { comment: "Looks fine" }));
  });

  it("will not reject without a reason", async () => {
    serve();
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: {} });
    renderWithProviders(<ApprovalsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Reject REQ-0005" }));
    fireEvent.click(screen.getByRole("button", { name: "Reject" }));
    expect(await screen.findByText("A comment is required to reject")).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText(/Reason for rejecting/), { target: { value: "Too expensive" } });
    fireEvent.click(screen.getByRole("button", { name: "Reject" }));

    await waitFor(() => expect(post).toHaveBeenCalledWith("/purchase-requests/5/reject", { comment: "Too expensive" }));
  });

  it("says when a decision is made on someone else's behalf", async () => {
    serve([queueItem({ on_behalf_of: person(9, "Boss Person") })]);
    renderWithProviders(<ApprovalsPage />);

    expect(await screen.findByText("on behalf of Boss Person")).toBeInTheDocument();
  });

  it("explains an empty queue", async () => {
    serve([]);
    renderWithProviders(<ApprovalsPage />);

    expect(await screen.findByText("Nothing is waiting for you")).toBeInTheDocument();
  });

  it("sends an order amendment decision to the amendment endpoint", async () => {
    serve([queueItem({ document_type: "purchase_order_amendment", document_id: 12, label: "PO-0007 v2" })]);
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: {} });
    renderWithProviders(<ApprovalsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Approve PO-0007 v2" }));
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() => expect(post).toHaveBeenCalledWith("/po-amendments/12/approve", undefined));
  });

  it("creates a delegation with a user number when the person cannot list users", async () => {
    serve();
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: delegation });
    renderWithProviders(<ApprovalsPage />);
    await screen.findByText("Laptops for new hires");

    fireEvent.click(screen.getByRole("button", { name: "Delegate approvals" }));
    expect(await screen.findByText("Choose who covers for you")).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Covered by (user number)"), { target: { value: "8" } });
    fireEvent.change(screen.getByLabelText("Away from"), { target: { value: "2026-11-01" } });
    fireEvent.change(screen.getByLabelText("Back on"), { target: { value: "2026-10-30" } });
    fireEvent.click(screen.getByRole("button", { name: "Delegate approvals" }));
    expect(await screen.findByText("The end date cannot be before the start date")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Back on"), { target: { value: "2026-11-10" } });
    fireEvent.click(screen.getByRole("button", { name: "Delegate approvals" }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/approval-delegations", {
        delegate_id: 8,
        starts_on: "2026-11-01",
        ends_on: "2026-11-10",
      }),
    );
  });

  it("revokes a delegation", async () => {
    serve([], [delegation]);
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: { ...delegation, revoked_at: "x" } });
    renderWithProviders(<ApprovalsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Revoke delegation to Dana Deputy" }));

    await waitFor(() => expect(post).toHaveBeenCalledWith("/approval-delegations/3/revoke"));
  });
});
