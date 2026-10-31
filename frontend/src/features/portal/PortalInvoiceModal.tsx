import { useRef, useState, type FormEvent } from "react";

import { extractErrorMessage } from "@/api/client";
import { useCreatePortalInvoice, usePortalOrder, usePortalOrders } from "@/api/portal";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";
import { useToast } from "@/components/ui/toast-context";

import { buildInvoicePayload, draftLinesFor, type InvoiceDraft, type InvoiceLineDraft } from "./portalInvoice";

const EMPTY: InvoiceDraft = { orderId: null, invoiceNumber: "", invoiceDate: "", dueDate: "", notes: "", lines: [] };
const ORDER_CHOICES = 100;

export function PortalInvoiceModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const { showToast } = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState<InvoiceDraft>(EMPTY);
  const [edits, setEdits] = useState<Record<number, Partial<InvoiceLineDraft>>>({});
  const [error, setError] = useState<string | null>(null);
  const { data: orders } = usePortalOrders(1, ORDER_CHOICES);
  const { data: order } = usePortalOrder(draft.orderId);
  const create = useCreatePortalInvoice();

  // Lines come from the chosen order (quantity and price pre-filled); only what the supplier edits is kept in `edits`.
  const baseLines = order && order.id === draft.orderId ? draftLinesFor(order.items) : [];
  const lines = baseLines.map((line) => ({ ...line, ...edits[line.product_id] }));

  const close = () => {
    setDraft(EMPTY);
    setEdits({});
    setError(null);
    onClose();
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const result = buildInvoicePayload({ ...draft, lines }, fileRef.current?.files?.[0] ?? null);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    setError(null);
    try {
      await create.mutateAsync({ input: result.input, file: fileRef.current!.files![0] });
      showToast("Invoice sent. Finance will review it.");
      close();
    } catch (failure) {
      setError(extractErrorMessage(failure));
    }
  };

  const setLine = (productId: number, field: "quantity" | "unit_price", value: string) =>
    setEdits((current) => ({ ...current, [productId]: { ...current[productId], [field]: value } }));

  return (
    <Modal isOpen={isOpen} onClose={close} title="New invoice" size="lg">
      <form onSubmit={(event) => void submit(event)} className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Label htmlFor="inv-order">Order</Label>
            <Select
              id="inv-order"
              value={draft.orderId ?? ""}
              onChange={(event) => {
                setEdits({});
                setDraft({ ...draft, orderId: event.target.value ? Number(event.target.value) : null });
              }}
            >
              <option value="">Choose an order…</option>
              {orders?.items.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.po_number}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="inv-number">Invoice number</Label>
            <Input
              id="inv-number"
              value={draft.invoiceNumber}
              onChange={(e) => setDraft({ ...draft, invoiceNumber: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="inv-date">Invoice date</Label>
            <Input
              id="inv-date"
              type="date"
              value={draft.invoiceDate}
              onChange={(e) => setDraft({ ...draft, invoiceDate: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="inv-due">Due date (optional)</Label>
            <Input
              id="inv-due"
              type="date"
              value={draft.dueDate}
              onChange={(e) => setDraft({ ...draft, dueDate: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="inv-file">Invoice file</Label>
            <input
              ref={fileRef}
              id="inv-file"
              type="file"
              accept="application/pdf,image/png,image/jpeg"
              className="block w-full text-sm"
            />
          </div>
        </div>
        {order && lines.length > 0 && (
          <div>
            <p className="mb-1 text-sm font-medium text-slate-700">Lines (set a quantity of 0 to leave one out)</p>
            {order.items.map((item) => (
              <div key={item.product_id} className="grid grid-cols-[1fr_6rem_8rem] items-center gap-2 py-1 text-sm">
                <span>{item.product_name}</span>
                <Input
                  aria-label={`Quantity of ${item.product_name}`}
                  inputMode="numeric"
                  value={lines.find((l) => l.product_id === item.product_id)?.quantity ?? ""}
                  onChange={(e) => setLine(item.product_id, "quantity", e.target.value)}
                />
                <Input
                  aria-label={`Unit price of ${item.product_name}`}
                  inputMode="decimal"
                  value={lines.find((l) => l.product_id === item.product_id)?.unit_price ?? ""}
                  onChange={(e) => setLine(item.product_id, "unit_price", e.target.value)}
                />
              </div>
            ))}
          </div>
        )}
        <div>
          <Label htmlFor="inv-notes">Notes (optional)</Label>
          <Input id="inv-notes" value={draft.notes} onChange={(e) => setDraft({ ...draft, notes: e.target.value })} />
        </div>
        {error && (
          <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-3">
          <Button type="button" variant="secondary" onClick={close}>
            Cancel
          </Button>
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Sending…" : "Send invoice"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
