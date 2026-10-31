import { fireEvent, screen, waitFor } from "@testing-library/react";
import { AxiosError, type AxiosResponse } from "axios";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import { renderWithProviders } from "@/test/render";

import { PurchaseOrderDocumentActions } from "./PurchaseOrderDocumentActions";

function renderActions(canSend: boolean) {
  renderWithProviders(<PurchaseOrderDocumentActions poId={7} poNumber="PO-0007" canSend={canSend} />);
}

describe("PurchaseOrderDocumentActions", () => {
  afterEach(() => vi.restoreAllMocks());

  it("downloads the PDF through the authenticated client as a blob", async () => {
    const blob = new Blob(["%PDF"], { type: "application/pdf" });
    const get = vi.spyOn(apiClient, "get").mockResolvedValue({ data: blob });
    const createObjectURL = vi.fn(() => "blob:pdf");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { ...URL, createObjectURL, revokeObjectURL });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    renderActions(false);

    fireEvent.click(screen.getByRole("button", { name: "Download PDF" }));

    await waitFor(() => expect(click).toHaveBeenCalled());
    expect(get).toHaveBeenCalledWith("/purchase-orders/7/pdf", { responseType: "blob" });
    expect(createObjectURL).toHaveBeenCalledWith(blob);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:pdf");
    vi.unstubAllGlobals();
  });

  it("hides Send to supplier unless the user may send", () => {
    renderActions(false);

    expect(screen.queryByRole("button", { name: "Send to supplier" })).not.toBeInTheDocument();
  });

  it("confirms a successful send", async () => {
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: undefined });
    renderActions(true);

    fireEvent.click(screen.getByRole("button", { name: "Send to supplier" }));

    expect(await screen.findByText(/on its way to the supplier/i)).toBeInTheDocument();
    expect(post).toHaveBeenCalledWith("/purchase-orders/7/send");
  });

  it("shows the server's reason when sending fails", async () => {
    vi.spyOn(apiClient, "post").mockRejectedValue(
      new AxiosError("bad", "ERR_BAD_REQUEST", undefined, undefined, {
        status: 422,
        data: { detail: "The supplier has no email address." },
      } as AxiosResponse),
    );
    renderActions(true);

    fireEvent.click(screen.getByRole("button", { name: "Send to supplier" }));

    expect(await screen.findByText("The supplier has no email address.")).toBeInTheDocument();
  });
});
