import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { ConfirmDialog } from "./ConfirmDialog";
import { Drawer } from "./Drawer";
import { Modal } from "./Modal";

function ModalHarness({ onClose }: { onClose?: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)}>Open dialog</button>
      <Modal
        isOpen={open}
        onClose={() => {
          onClose?.();
          setOpen(false);
        }}
        title="Edit supplier"
        description="Change the details"
      >
        <button>First</button>
        <button>Last</button>
      </Modal>
    </>
  );
}

function openModal() {
  const trigger = screen.getByRole("button", { name: "Open dialog" });
  trigger.focus();
  fireEvent.click(trigger);
  return trigger;
}

describe("Modal", () => {
  it("is a labelled, described, modal dialog that moves focus inside", () => {
    render(<ModalHarness />);
    openModal();
    const dialog = screen.getByRole("dialog", { name: "Edit supplier" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAccessibleDescription("Change the details");
    expect(screen.getByRole("button", { name: "First" })).toHaveFocus();
  });

  it("traps Tab and Shift+Tab inside the dialog", () => {
    render(<ModalHarness />);
    openModal();
    screen.getByRole("button", { name: "Last" }).focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(screen.getByRole("button", { name: "Close" })).toHaveFocus();
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(screen.getByRole("button", { name: "Last" })).toHaveFocus();
  });

  it("closes on Escape and returns focus to the trigger", () => {
    const onClose = vi.fn();
    render(<ModalHarness onClose={onClose} />);
    const trigger = openModal();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("locks page scroll while open and releases it after", () => {
    render(<ModalHarness />);
    openModal();
    expect(document.body.style.overflow).toBe("hidden");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(document.body.style.overflow).toBe("");
  });

  it("can ignore backdrop clicks", () => {
    const onClose = vi.fn();
    const { container } = render(
      <Modal isOpen onClose={onClose} title="Unsaved" closeOnBackdrop={false}>
        body
      </Modal>,
    );
    fireEvent.click(container.querySelector(".scrim")!);
    expect(onClose).not.toHaveBeenCalled();
  });
});

describe("Drawer", () => {
  it("renders nothing when closed and a modal dialog when open, closing on Escape", () => {
    const onClose = vi.fn();
    const { rerender } = render(
      <Drawer isOpen={false} onClose={onClose} title="History">
        <button>Row</button>
      </Drawer>,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    rerender(
      <Drawer isOpen onClose={onClose} title="History">
        <button>Row</button>
      </Drawer>,
    );
    expect(screen.getByRole("dialog", { name: "History" })).toHaveAttribute("aria-modal", "true");
    expect(screen.getByRole("button", { name: "Row" })).toHaveFocus();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });

  it("answers Escape in the top overlay only when dialogs are stacked", () => {
    const closeDrawer = vi.fn();
    const closeConfirm = vi.fn();
    const view = (confirmOpen: boolean) => (
      <Drawer isOpen onClose={closeDrawer} title="Supplier">
        <ConfirmDialog
          isOpen={confirmOpen}
          title="Discard?"
          message="Lose edits"
          onConfirm={vi.fn()}
          onCancel={closeConfirm}
        />
      </Drawer>
    );
    // The confirm dialog opens after the drawer, as it would from a button inside it.
    const { rerender } = render(view(false));
    rerender(view(true));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(closeConfirm).toHaveBeenCalledTimes(1);
    expect(closeDrawer).not.toHaveBeenCalled();
  });
});

describe("ConfirmDialog", () => {
  it("confirms and cancels, and focuses Cancel first for a destructive action", () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(
      <ConfirmDialog
        isOpen
        variant="danger"
        title="Delete supplier"
        message="This cannot be undone."
        confirmLabel="Delete"
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    );
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(onConfirm).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalled();
  });

  it("requires the exact text before a typed confirmation enables the button", () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog
        isOpen
        variant="danger"
        title="Anonymise user"
        message="Irreversible."
        confirmLabel="Anonymise"
        confirmText="ANONYMISE"
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />,
    );
    const input = screen.getByLabelText(/Type ANONYMISE to confirm/);
    expect(input).toHaveFocus();
    const confirm = screen.getByRole("button", { name: "Anonymise" });
    expect(confirm).toBeDisabled();
    fireEvent.change(input, { target: { value: "anonymise" } });
    expect(confirm).toBeDisabled();
    fireEvent.change(input, { target: { value: "ANONYMISE" } });
    expect(confirm).toBeEnabled();
    fireEvent.click(confirm);
    expect(onConfirm).toHaveBeenCalled();
  });

  it("clears the typed text when reopened and blocks both buttons correctly while loading", () => {
    const props = { title: "Delete", message: "m", confirmText: "DELETE", onConfirm: vi.fn(), onCancel: vi.fn() };
    const { rerender } = render(<ConfirmDialog isOpen {...props} />);
    fireEvent.change(screen.getByLabelText(/Type DELETE/), { target: { value: "DELETE" } });
    rerender(<ConfirmDialog isOpen={false} {...props} />);
    rerender(<ConfirmDialog isOpen isLoading {...props} />);
    expect(screen.getByLabelText(/Type DELETE/)).toHaveValue("");
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Please wait/ })).toHaveAttribute("aria-busy", "true");
  });
});
