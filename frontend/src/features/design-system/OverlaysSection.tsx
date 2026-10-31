import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Drawer } from "@/components/ui/Drawer";
import { FormField } from "@/components/ui/FormField";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";

import { Section, SubHeading } from "./showcase";

type Open = null | "modal" | "drawer" | "confirm" | "danger" | "typed" | "nested";

/** Synthetic key presses, so the buttons below do exactly what the keyboard shortcut does. */
function press(init: KeyboardEventInit) {
  document.body.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, ...init }));
}

export function OverlaysSection() {
  const [open, setOpen] = useState<Open>(null);
  const close = () => setOpen(null);

  return (
    <Section
      id="overlays"
      title="Dialogs, drawer and command palette"
      intro="Overlays trap focus, close on Escape, return focus to the button that opened them and lock page scroll. Switch the theme at the top to see them in dark. Stacked overlays answer Escape one at a time."
    >
      <div className="space-y-4">
        <div>
          <SubHeading>Open</SubHeading>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => setOpen("modal")}>
              Modal
            </Button>
            <Button variant="secondary" onClick={() => setOpen("drawer")}>
              Drawer
            </Button>
            <Button variant="secondary" onClick={() => setOpen("confirm")}>
              Confirm
            </Button>
            <Button variant="secondary" onClick={() => setOpen("danger")}>
              Confirm (destructive)
            </Button>
            <Button variant="secondary" onClick={() => setOpen("typed")}>
              Confirm (typed)
            </Button>
            <Button variant="secondary" onClick={() => setOpen("nested")}>
              Drawer with confirm on top
            </Button>
            <Button variant="secondary" onClick={() => press({ key: "k", ctrlKey: true })}>
              Command palette (Ctrl+K)
            </Button>
            <Button variant="secondary" onClick={() => press({ key: "?", shiftKey: true })}>
              Shortcut help (?)
            </Button>
          </div>
        </div>
      </div>

      <Modal
        isOpen={open === "modal"}
        onClose={close}
        title="Edit supplier"
        description="Changes apply to new orders only."
        footer={
          <>
            <Button variant="secondary" onClick={close}>
              Cancel
            </Button>
            <Button onClick={close}>Save supplier</Button>
          </>
        }
      >
        <div className="space-y-4">
          <FormField label="Supplier name" required>
            <Input defaultValue="Acme Supplies" />
          </FormField>
          <FormField label="Contact email" error="Enter a valid email address">
            <Input defaultValue="ap@acme" />
          </FormField>
        </div>
      </Modal>

      <Drawer
        isOpen={open === "drawer" || open === "nested"}
        onClose={close}
        title="Order history"
        footer={
          open === "nested" ? (
            <Button variant="danger" onClick={() => setOpen("danger")}>
              Discard changes
            </Button>
          ) : (
            <Button variant="secondary" onClick={close}>
              Close
            </Button>
          )
        }
      >
        <p className="text-sm text-text-secondary">
          Eight events. Tab stays inside the drawer; Escape closes it and returns focus to the button.
        </p>
      </Drawer>

      <ConfirmDialog
        isOpen={open === "confirm"}
        title="Submit for approval"
        message="The request goes to Finance and can no longer be edited."
        confirmLabel="Submit"
        onConfirm={close}
        onCancel={close}
      />
      <ConfirmDialog
        isOpen={open === "danger"}
        variant="danger"
        title="Delete supplier"
        message="Orders that use this supplier keep their copy. This cannot be undone."
        confirmLabel="Delete supplier"
        onConfirm={close}
        onCancel={close}
      />
      <ConfirmDialog
        isOpen={open === "typed"}
        variant="danger"
        title="Anonymise user"
        message="Personal data is erased permanently."
        confirmLabel="Anonymise"
        confirmText="ANONYMISE"
        onConfirm={close}
        onCancel={close}
      />
    </Section>
  );
}
