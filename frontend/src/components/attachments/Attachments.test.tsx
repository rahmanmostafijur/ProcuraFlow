import { fireEvent, screen, waitFor } from "@testing-library/react";
import axios from "axios";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import type { Attachment } from "@/api/types";
import { person } from "@/test/fixtures";
import { mockGet, renderWithProviders } from "@/test/render";

import { Attachments } from "./Attachments";

const attachment: Attachment = {
  id: 4,
  parent_type: "purchase_request",
  parent_id: 5,
  filename: "quote.pdf",
  content_type: "application/pdf",
  size_bytes: 2048,
  uploaded_by: person(1, "Me Myself"),
  created_at: "2026-10-20T09:00:00Z",
};

function pick(file: File) {
  fireEvent.change(screen.getByLabelText("Choose a file to attach"), { target: { files: [file] } });
}

describe("Attachments", () => {
  afterEach(() => vi.restoreAllMocks());

  it("lists files with size and uploader", async () => {
    mockGet({ "/attachments": [attachment] });
    renderWithProviders(<Attachments parentType="purchase_request" parentId={5} canWrite />);

    expect(await screen.findByText("quote.pdf")).toBeInTheDocument();
    expect(screen.getByText(/2\.0 KB/)).toBeInTheDocument();
  });

  it("uploads the chosen file as multipart form data for this record", async () => {
    mockGet({ "/attachments": [] });
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: attachment });
    renderWithProviders(<Attachments parentType="purchase_request" parentId={5} canWrite />);
    await screen.findByText("No files attached.");

    pick(new File(["%PDF-1.4"], "invoice.pdf", { type: "application/pdf" }));

    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    const [url, body, config] = post.mock.calls[0];
    expect(url).toBe("/attachments");
    expect((body as FormData).get("file")).toBeInstanceOf(File);
    expect(config).toMatchObject({ params: { parent_type: "purchase_request", parent_id: 5 } });
  });

  it("refuses a file over 10 MB without calling the API", async () => {
    mockGet({ "/attachments": [] });
    const post = vi.spyOn(apiClient, "post");
    renderWithProviders(<Attachments parentType="purchase_request" parentId={5} canWrite />);
    await screen.findByText("No files attached.");
    const big = new File(["x"], "big.pdf", { type: "application/pdf" });
    Object.defineProperty(big, "size", { value: 10 * 1024 * 1024 + 1 });

    pick(big);

    expect(await screen.findByText(/larger than 10 MB/)).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();
  });

  it("shows the API's reason when it refuses a file", async () => {
    mockGet({ "/attachments": [] });
    vi.spyOn(apiClient, "post").mockRejectedValue(
      new axios.AxiosError("bad", "415", undefined, undefined, {
        status: 415,
        data: { detail: "Attach a PDF, PNG or JPEG file." },
      } as never),
    );
    renderWithProviders(<Attachments parentType="purchase_request" parentId={5} canWrite />);
    await screen.findByText("No files attached.");

    pick(new File(["hello"], "notes.txt", { type: "text/plain" }));

    expect(await screen.findByText("Attach a PDF, PNG or JPEG file.")).toBeInTheDocument();
  });

  it("offers no upload or delete when the user cannot write", async () => {
    mockGet({ "/attachments": [attachment] });
    renderWithProviders(<Attachments parentType="purchase_request" parentId={5} canWrite={false} />);

    await screen.findByText("quote.pdf");
    expect(screen.queryByLabelText("Choose a file to attach")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remove quote.pdf" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download quote.pdf" })).toBeInTheDocument();
  });

  it("removes a file", async () => {
    mockGet({ "/attachments": [attachment] });
    const del = vi.spyOn(apiClient, "delete").mockResolvedValue({ data: null });
    renderWithProviders(<Attachments parentType="purchase_request" parentId={5} canWrite />);

    fireEvent.click(await screen.findByRole("button", { name: "Remove quote.pdf" }));

    await waitFor(() => expect(del).toHaveBeenCalledWith("/attachments/4"));
  });
});
