import { fireEvent, screen, waitFor } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import type { Invoice } from "@/api/supplierInvoices";
import type { QueueItem } from "@/api/types";
import { queueItem } from "@/test/fixtures";
import { mockGet, renderWithProviders } from "@/test/render";

import { invoice } from "./invoice-fixtures";
import { InvoiceDetailPage } from "./InvoiceDetailPage";

function show(doc: Invoice, permissions: string[], queue: QueueItem[] = []) {
  mockGet({
    "/supplier-invoices/3": doc,
    "/supplier-invoices/3/payments": [],
    "/approvals/queue": { items: queue, total: queue.length },
    "/approvals/invoice_exception/3/steps": [],
  });
  renderWithProviders(
    <Routes>
      <Route path="/invoices/:id" element={<InvoiceDetailPage />} />
    </Routes>,
    { permissions, route: "/invoices/3" },
  );
}

const buttonNames = () => screen.queryAllByRole("button").map((button) => button.textContent);

describe("InvoiceDetailPage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("offers approve, reject, hold and void on a matched invoice to an approver who is not its creator", async () => {
    show(invoice(), ["invoice:read", "invoice:write", "invoice:approve"]);

    expect(await screen.findByRole("button", { name: "Approve" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Put on hold" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Void invoice" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Record payment" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Submit for matching" })).not.toBeInTheDocument();
  });

  it("shows no action to a read-only user", async () => {
    show(invoice(), ["invoice:read"]);

    await screen.findByRole("heading", { name: "INV-0003" });
    expect(buttonNames().filter((name) => /Approve|Reject|hold|Void|payment|Submit/.test(name ?? ""))).toEqual([]);
  });

  it("does not let the creator approve a matched invoice of their own", async () => {
    show(invoice({ created_by: 1 }), ["invoice:read", "invoice:approve"]);

    expect(await screen.findByText(/another approver must approve it/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });

  it("offers Approve on an exception only when it is in the user's approval queue", async () => {
    const doc = invoice({
      status: "exception",
      exception_reasons: [
        { code: "PRICE_VARIANCE", message: "Price 60 against 50 ordered", line: 1, duplicate_of: null },
      ],
    });
    show(doc, ["invoice:read"], [queueItem({ document_type: "invoice_exception", document_id: 3 })]);

    expect(await screen.findByRole("button", { name: "Approve" })).toBeInTheDocument();
    expect(screen.getByText("Price differs from the order")).toBeInTheDocument();
  });

  it("offers Submit on a draft and Record payment on an approved invoice with the payment permission", async () => {
    show(invoice({ status: "draft" }), ["invoice:read", "invoice:write", "payment:write"]);
    expect(await screen.findByRole("button", { name: "Submit for matching" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Record payment" })).not.toBeInTheDocument();
  });

  it("offers Record payment on an approved invoice only with payment:write", async () => {
    show(invoice({ status: "approved" }), ["invoice:read", "payment:write"]);
    expect(await screen.findByRole("button", { name: "Record payment" })).toBeInTheDocument();
  });

  it("calls the approve endpoint when the dialog is confirmed", async () => {
    show(invoice(), ["invoice:read", "invoice:approve"]);
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: invoice({ status: "approved" }) });

    fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(dialog.querySelector("button[type=submit]") as HTMLElement);

    await waitFor(() => expect(post).toHaveBeenCalledWith("/supplier-invoices/3/approve", {}));
  });

  it("requires a reason before voiding, then calls the void endpoint", async () => {
    show(invoice(), ["invoice:read", "invoice:write"]);
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: invoice({ status: "void" }) });

    fireEvent.click(await screen.findByRole("button", { name: "Void invoice" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(dialog.querySelector("button[type=submit]") as HTMLElement);
    expect(await screen.findByText("A reason is required")).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText(/Reason/), { target: { value: "Entered twice" } });
    fireEvent.click(dialog.querySelector("button[type=submit]") as HTMLElement);

    await waitFor(() => expect(post).toHaveBeenCalledWith("/supplier-invoices/3/void", { reason: "Entered twice" }));
  });
});
