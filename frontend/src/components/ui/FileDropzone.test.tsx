import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FileDropzone } from "./FileDropzone";
import { formatFileSize, validateFile } from "./file-validation";

const file = (name: string, type: string, size = 1024) => {
  const f = new File(["x"], name, { type });
  Object.defineProperty(f, "size", { value: size });
  return f;
};

const input = () => screen.getByLabelText<HTMLInputElement>(/Upload files/, { selector: "input" });

describe("file validation", () => {
  it("checks extension, MIME wildcard, size and emptiness", () => {
    expect(validateFile(file("a.pdf", "application/pdf"), { accept: [".pdf"] })).toBeNull();
    expect(validateFile(file("a.PNG", "image/png"), { accept: ["image/*"] })).toBeNull();
    expect(validateFile(file("a.exe", "application/x-msdownload"), { accept: [".pdf", "image/*"] })).toMatch(/Only/);
    expect(validateFile(file("a.pdf", "application/pdf", 5_000_000), { maxSizeBytes: 1_000_000 })).toMatch(
      /larger than/,
    );
    expect(validateFile(file("a.pdf", "application/pdf", 0), {})).toBe("The file is empty.");
  });

  it("formats sizes with Intl units", () => {
    expect(formatFileSize(512)).toContain("512");
    expect(formatFileSize(2048)).toContain("2");
    expect(formatFileSize(5 * 1024 * 1024)).toContain("5");
  });
});

describe("FileDropzone", () => {
  it("has a real, labelled file input so keyboard and click both open the picker", () => {
    render(<FileDropzone onFilesAccepted={vi.fn()} accept={[".pdf"]} maxSizeBytes={1024 * 1024} />);
    expect(input()).toHaveAttribute("type", "file");
    expect(input()).toHaveAttribute("accept", ".pdf");
    expect(input()).toHaveAccessibleDescription(/Allowed: \.pdf/);
  });

  it("passes valid chosen files on and reports none rejected", () => {
    const onFilesAccepted = vi.fn();
    render(<FileDropzone onFilesAccepted={onFilesAccepted} accept={[".pdf"]} />);
    const pdf = file("invoice.pdf", "application/pdf");
    fireEvent.change(input(), { target: { files: [pdf] } });
    expect(onFilesAccepted).toHaveBeenCalledWith([pdf]);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("explains a wrong type and an oversized file, and accepts the rest", () => {
    const onFilesAccepted = vi.fn();
    const onFilesRejected = vi.fn();
    render(
      <FileDropzone
        onFilesAccepted={onFilesAccepted}
        onFilesRejected={onFilesRejected}
        accept={[".pdf"]}
        maxSizeBytes={1000}
      />,
    );
    const good = file("ok.pdf", "application/pdf", 500);
    fireEvent.change(input(), {
      target: {
        files: [good, file("virus.exe", "application/x-msdownload"), file("big.pdf", "application/pdf", 5000)],
      },
    });
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("virus.exe: Only .pdf files are allowed.");
    expect(alert).toHaveTextContent("big.pdf: The file is larger than");
    expect(onFilesAccepted).toHaveBeenCalledWith([good]);
    expect(onFilesRejected).toHaveBeenCalledWith([
      expect.objectContaining({ name: "virus.exe" }),
      expect.objectContaining({ name: "big.pdf" }),
    ]);
  });

  it("validates dropped files the same way and highlights while dragging", () => {
    const onFilesAccepted = vi.fn();
    render(<FileDropzone onFilesAccepted={onFilesAccepted} accept={["image/*"]} />);
    const zone = input().closest("label")!;
    fireEvent.dragOver(zone);
    expect(screen.getByText("Drop to upload")).toBeInTheDocument();
    const png = file("a.png", "image/png");
    fireEvent.drop(zone, { dataTransfer: { files: [png, file("a.txt", "text/plain")] } });
    expect(onFilesAccepted).toHaveBeenCalledWith([png]);
    expect(screen.getByRole("alert")).toHaveTextContent("a.txt");
    expect(screen.queryByText("Drop to upload")).not.toBeInTheDocument();
  });

  it("only takes one file when multiple is off", () => {
    const onFilesAccepted = vi.fn();
    render(<FileDropzone onFilesAccepted={onFilesAccepted} multiple={false} />);
    const a = file("a.pdf", "application/pdf");
    fireEvent.change(input(), { target: { files: [a, file("b.pdf", "application/pdf")] } });
    expect(onFilesAccepted).toHaveBeenCalledWith([a]);
  });

  it("lists files with progress, errors and a labelled remove button", () => {
    const onRemove = vi.fn();
    render(
      <FileDropzone
        onFilesAccepted={vi.fn()}
        onRemove={onRemove}
        items={[
          { id: "1", name: "a.pdf", size: 2048, status: "uploading", progress: 40 },
          { id: "2", name: "b.pdf", size: 2048, status: "done" },
          { id: "3", name: "c.pdf", size: 2048, status: "error", error: "Virus found" },
        ]}
      />,
    );
    expect(screen.getByRole("progressbar", { name: "Uploading a.pdf" })).toHaveAttribute("value", "40");
    expect(screen.getByText(/Uploaded/)).toBeInTheDocument();
    expect(screen.getByText(/Virus found/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Remove b.pdf" }));
    expect(onRemove).toHaveBeenCalledWith("2");
  });

  it("does not take files while disabled", () => {
    const onFilesAccepted = vi.fn();
    render(<FileDropzone onFilesAccepted={onFilesAccepted} disabled />);
    expect(input()).toBeDisabled();
    fireEvent.drop(input().closest("label")!, { dataTransfer: { files: [file("a.pdf", "application/pdf")] } });
    expect(onFilesAccepted).not.toHaveBeenCalled();
  });
});
