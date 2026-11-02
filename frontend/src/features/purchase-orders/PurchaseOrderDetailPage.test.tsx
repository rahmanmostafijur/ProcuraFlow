import { fireEvent, screen, waitFor } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import type { PurchaseOrder, QueueItem } from "@/api/types";
import { purchaseOrder, queueItem } from "@/test/fixtures";
import { mockGet, renderWithProviders } from "@/test/render";

import { PurchaseOrderDetailPage } from "./PurchaseOrderDetailPage";

function show(po: PurchaseOrder, permissions: string[], queue: QueueItem[] = []) {
  mockGet({
    "/purchase-orders/7": po,
    "/purchase-orders/7/versions": [],
    "/approvals/queue": { items: queue, total: queue.length },
    "/approvals/purchase_order/7/steps": [],
    "/attachments": [],
    "/cost-centres": [{ id: 4, code: "IT", name: "Information Technology", manager_id: null, is_active: true }],
    "/products": { items: [], total: 0, page: 1, page_size: 100, total_pages: 1 },
    "/tax-rates": [],
  });
  renderWithProviders(
    <Routes>
      <Route path="/purchase-orders/:id" element={<PurchaseOrderDetailPage />} />
    </Routes>,
    { permissions, route: "/purchase-orders/7" },
  );
}

const inQueue = [queueItem({ document_type: "purchase_order", document_id: 7, label: "PO-0007" })];

describe("PurchaseOrderDetailPage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows Approve and Reject when the order is in the user's queue, and the cost centre", async () => {
    show(purchaseOrder(), ["po:approve"], inQueue);

    expect(await screen.findByRole("button", { name: "Approve" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();
    expect(await screen.findByText("IT — Information Technology")).toBeInTheDocument();
  });

  it("hides Approve and Reject from an approver whose queue does not hold the order", async () => {
    show(purchaseOrder(), ["po:approve"], []);

    await screen.findByRole("heading", { name: "PO-0007" });
    await screen.findByText("IT — Information Technology");
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reject" })).not.toBeInTheDocument();
  });

  it("explains that rejecting cancels the order and needs a comment", async () => {
    show(purchaseOrder(), ["po:approve"], inQueue);
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: purchaseOrder({ status: "cancelled" }) });

    fireEvent.click(await screen.findByRole("button", { name: "Reject" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("A rejected purchase order is cancelled");
    fireEvent.click(dialog.querySelector("button[type=submit]") as HTMLElement);
    expect(await screen.findByText("A comment is required to reject")).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText(/Reason for rejecting/), { target: { value: "Wrong supplier" } });
    fireEvent.click(dialog.querySelector("button[type=submit]") as HTMLElement);

    await waitFor(() => expect(post).toHaveBeenCalledWith("/purchase-orders/7/reject", { comment: "Wrong supplier" }));
  });

  it("offers Amend to someone who may transition an ordered order", async () => {
    show(purchaseOrder({ status: "ordered" }), ["po:transition"]);

    expect(await screen.findByRole("button", { name: "Amend" })).toBeInTheDocument();
    expect(await screen.findByText("Versions")).toBeInTheDocument();
  });

  it("does not offer Amend without po:transition or on an order that is not yet approved", async () => {
    show(purchaseOrder({ status: "ordered" }), ["po:create"]);
    await screen.findByRole("heading", { name: "PO-0007" });
    expect(screen.queryByRole("button", { name: "Amend" })).not.toBeInTheDocument();
  });

  it("does not offer Amend on a draft", async () => {
    show(purchaseOrder({ status: "draft" }), ["po:transition"]);

    await screen.findByRole("heading", { name: "PO-0007" });
    expect(screen.queryByRole("button", { name: "Amend" })).not.toBeInTheDocument();
    expect(screen.queryByText("Versions")).not.toBeInTheDocument();
  });
});
