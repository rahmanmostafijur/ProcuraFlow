import { fireEvent, screen, waitFor } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import type { PurchaseRequest, QueueItem } from "@/api/types";
import { person, purchaseRequest, queueItem } from "@/test/fixtures";
import { mockGet, renderWithProviders } from "@/test/render";

import { RequestDetailPage } from "./RequestDetailPage";

function show(request: PurchaseRequest, permissions: string[], queue: QueueItem[] = []) {
  mockGet({
    "/purchase-requests/5": request,
    "/cost-centres": [],
    "/approvals/queue": { items: queue, total: queue.length },
    "/approvals/purchase_request/5/steps": [],
    "/attachments": [],
    "/suppliers": { items: [], total: 0, page: 1, page_size: 100, total_pages: 1 },
    "/products": { items: [], total: 0, page: 1, page_size: 100, total_pages: 1 },
  });
  renderWithProviders(
    <Routes>
      <Route path="/requests/:id" element={<RequestDetailPage />} />
      <Route path="/purchase-orders/:id" element={<p>Order page</p>} />
    </Routes>,
    { permissions, route: "/requests/5" },
  );
}

const buttonNames = () => screen.getAllByRole("button").map((button) => button.textContent);

describe("RequestDetailPage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("offers the owner Edit, Submit and Cancel on a draft, and nothing to decide", async () => {
    show(purchaseRequest({ status: "draft" }), ["request:create"]);

    expect(await screen.findByRole("button", { name: "Edit" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel request" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Create purchase orders" })).not.toBeInTheDocument();
  });

  it("submits a draft", async () => {
    show(purchaseRequest({ status: "draft" }), ["request:create"]);
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: purchaseRequest({ status: "submitted" }) });

    fireEvent.click(await screen.findByRole("button", { name: "Submit" }));

    await waitFor(() => expect(post).toHaveBeenCalledWith("/purchase-requests/5/submit", undefined));
  });

  it("lets the owner only cancel once submitted", async () => {
    show(purchaseRequest({ status: "submitted" }), ["request:create"]);

    await screen.findByRole("button", { name: "Cancel request" });
    expect(buttonNames()).not.toContain("Edit");
    expect(buttonNames()).not.toContain("Submit");
  });

  it("shows the rejection reason and lets the owner edit and resubmit", async () => {
    show(purchaseRequest({ status: "rejected", rejection_reason: "Over budget" }), ["request:create"]);

    expect(await screen.findByText("Rejected: Over budget")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit" })).toBeInTheDocument();
  });

  it("shows Approve and Reject only to someone with the request in their queue", async () => {
    show(purchaseRequest({ status: "submitted", requester: person(2, "Rita") }), ["request:approve"], [queueItem()]);

    expect(await screen.findByRole("button", { name: "Approve" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
  });

  it("hides Approve from an approver whose queue does not hold the request", async () => {
    show(purchaseRequest({ status: "submitted", requester: person(2, "Rita") }), ["request:approve"], []);

    await screen.findByText("Laptops for new hires");
    await waitFor(() => expect(screen.queryByText("Loading request…")).not.toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reject" })).not.toBeInTheDocument();
  });

  it("needs a comment to reject", async () => {
    show(purchaseRequest({ status: "submitted", requester: person(2, "Rita") }), ["request:approve"], [queueItem()]);
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: purchaseRequest({ status: "rejected" }) });

    fireEvent.click(await screen.findByRole("button", { name: "Reject" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(dialog.querySelector("button[type=submit]") as HTMLElement);
    expect(await screen.findByText("A comment is required to reject")).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText(/Reason for rejecting/), { target: { value: "No budget" } });
    fireEvent.click(dialog.querySelector("button[type=submit]") as HTMLElement);

    await waitFor(() => expect(post).toHaveBeenCalledWith("/purchase-requests/5/reject", { comment: "No budget" }));
  });

  it("offers the order creator Create purchase orders only once approved", async () => {
    show(purchaseRequest({ status: "approved", requester: person(2, "Rita") }), ["po:create"]);

    expect(await screen.findByRole("button", { name: "Create purchase orders" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancel request" })).not.toBeInTheDocument();
  });

  it("hides Create purchase orders from someone without po:create", async () => {
    show(purchaseRequest({ status: "approved", requester: person(2, "Rita") }), ["request:read_all"]);

    await screen.findByText("Laptops for new hires");
    expect(screen.queryByRole("button", { name: "Create purchase orders" })).not.toBeInTheDocument();
  });
});
