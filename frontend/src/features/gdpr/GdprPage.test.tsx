import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import * as download from "@/lib/download";
import { apiError } from "@/test/apiError";
import { mockGet, renderWithProviders } from "@/test/render";

import { GdprPage } from "./GdprPage";

const users = {
  items: [{ id: 4, full_name: "Ada Admin", email: "ada@example.com", is_active: true }],
  total: 1,
  page: 1,
  page_size: 20,
  total_pages: 1,
};

function serve() {
  return mockGet({
    "/users": users,
    "/suppliers": { items: [], total: 0, page: 1, page_size: 20, total_pages: 0 },
    "/gdpr/users/4/export": { email: "ada@example.com" },
  });
}

async function openDialog() {
  renderWithProviders(<GdprPage />, { permissions: ["gdpr:manage"] });
  fireEvent.click(await screen.findByRole("button", { name: "Anonymise Ada Admin" }));
}

describe("GdprPage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("keeps the anonymise button disabled until the confirmation word is typed", async () => {
    serve();
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: {} });
    await openDialog();

    const confirm = screen.getByRole("button", { name: "Anonymise" });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Type ANONYMISE to confirm"), { target: { value: "anonymise" } });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Type ANONYMISE to confirm"), { target: { value: "ANONYMISE" } });
    expect(confirm).toBeEnabled();
    expect(post).not.toHaveBeenCalled();

    fireEvent.click(confirm);
    await waitFor(() => expect(post).toHaveBeenCalledWith("/gdpr/users/4/anonymise"));
  });

  it("shows the server's reason when the last active admin cannot be anonymised", async () => {
    serve();
    vi.spyOn(apiClient, "post").mockRejectedValue(apiError(409, "The last active admin cannot be anonymised"));
    await openDialog();

    fireEvent.change(screen.getByLabelText("Type ANONYMISE to confirm"), { target: { value: "ANONYMISE" } });
    fireEvent.click(screen.getByRole("button", { name: "Anonymise" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("The last active admin cannot be anonymised");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("saves the export as a JSON file", async () => {
    serve();
    const save = vi.spyOn(download, "saveBlob").mockImplementation(() => undefined);
    renderWithProviders(<GdprPage />, { permissions: ["gdpr:manage"] });

    fireEvent.click(await screen.findByRole("button", { name: "Export data of Ada Admin" }));

    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    expect(save.mock.calls[0][1]).toBe("gdpr-users-4.json");
  });

  it("anonymises a supplier contact through the contact endpoint", async () => {
    mockGet({
      "/users": users,
      "/suppliers": {
        items: [{ id: 9, name: "Acme", contact_name: "Cleo Contact", email: null }],
        total: 1,
        page: 1,
        page_size: 20,
        total_pages: 1,
      },
    });
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: {} });
    renderWithProviders(<GdprPage />, { permissions: ["gdpr:manage"] });

    fireEvent.click(screen.getByRole("tab", { name: "Supplier contacts" }));
    fireEvent.click(await screen.findByRole("button", { name: "Anonymise Cleo Contact" }));
    fireEvent.change(screen.getByLabelText("Type ANONYMISE to confirm"), { target: { value: "ANONYMISE" } });
    fireEvent.click(screen.getByRole("button", { name: "Anonymise" }));

    await waitFor(() => expect(post).toHaveBeenCalledWith("/gdpr/suppliers/9/contact/anonymise"));
  });
});
