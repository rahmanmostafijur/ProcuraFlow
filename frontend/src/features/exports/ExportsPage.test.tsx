import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import * as download from "@/lib/download";
import { renderWithProviders } from "@/test/render";

import { ExportsPage } from "./ExportsPage";

describe("ExportsPage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("asks for the bills export with only the filters that were filled in", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue({ data: new Blob(["a,b"]) });
    const save = vi.spyOn(download, "saveBlob").mockImplementation(() => undefined);
    renderWithProviders(<ExportsPage />);

    fireEvent.change(screen.getByLabelText("Bills for QuickBooks Online from date"), {
      target: { value: "2026-01-01" },
    });
    fireEvent.change(screen.getByLabelText("Bills for QuickBooks Online status"), { target: { value: "approved" } });
    fireEvent.click(screen.getByRole("button", { name: "Download Bills for QuickBooks Online" }));

    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    expect(get).toHaveBeenCalledWith("/exports/bills/quickbooks.csv", {
      params: { date_from: "2026-01-01", status: "approved" },
      responseType: "blob",
    });
    expect(save.mock.calls[0][1]).toBe("bills-quickbooks.csv");
  });

  it("sends no filters at all when none were chosen", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue({ data: new Blob(["x"]) });
    vi.spyOn(download, "saveBlob").mockImplementation(() => undefined);
    renderWithProviders(<ExportsPage />);

    fireEvent.click(screen.getByRole("button", { name: "Download Suppliers" }));

    await waitFor(() =>
      expect(get).toHaveBeenCalledWith("/exports/suppliers.csv", { params: {}, responseType: "blob" }),
    );
  });

  it("offers a status filter only for exports that have statuses", () => {
    renderWithProviders(<ExportsPage />);

    expect(screen.getByLabelText("Supplier invoices status")).toBeInTheDocument();
    expect(screen.queryByLabelText("Suppliers status")).not.toBeInTheDocument();
  });

  it("tells the person when the download fails", async () => {
    vi.spyOn(apiClient, "get").mockRejectedValue(new Error("boom"));
    renderWithProviders(<ExportsPage />);

    fireEvent.click(screen.getByRole("button", { name: "Download Purchase orders" }));

    expect(await screen.findByText("The export could not be downloaded. Please try again.")).toBeInTheDocument();
  });
});
