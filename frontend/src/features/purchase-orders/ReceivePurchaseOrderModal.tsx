import { useEffect, useState } from "react";

import type { PurchaseOrder } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Modal } from "@/components/ui/Modal";

interface ReceivePurchaseOrderModalProps {
  isOpen: boolean;
  onClose: () => void;
  purchaseOrder: PurchaseOrder;
  onSubmit: (items: { product_id: number; quantity: number }[]) => Promise<void>;
  isSubmitting: boolean;
}

export function ReceivePurchaseOrderModal({
  isOpen,
  onClose,
  purchaseOrder,
  onSubmit,
  isSubmitting,
}: ReceivePurchaseOrderModalProps) {
  const [quantities, setQuantities] = useState<Record<number, number>>({});

  useEffect(() => {
    if (isOpen) {
      const initial: Record<number, number> = {};
      for (const item of purchaseOrder.items) {
        const remaining = item.quantity - item.received_quantity;
        if (remaining > 0) initial[item.product_id] = remaining;
      }
      setQuantities(initial);
    }
  }, [isOpen, purchaseOrder]);

  const pendingItems = purchaseOrder.items.filter((item) => item.quantity - item.received_quantity > 0);

  const handleSubmit = async () => {
    const items = pendingItems
      .map((item) => ({ product_id: item.product_id, quantity: quantities[item.product_id] ?? 0 }))
      .filter((item) => item.quantity > 0);
    await onSubmit(items);
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Receive stock — ${purchaseOrder.po_number}`}>
      <div className="space-y-4">
        {pendingItems.length === 0 ? (
          <p className="text-sm text-slate-500">All items on this order have already been received.</p>
        ) : (
          <div className="space-y-3">
            {pendingItems.map((item) => {
              const remaining = item.quantity - item.received_quantity;
              return (
                <div key={item.id} className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-slate-800">Product #{item.product_id}</p>
                    <p className="text-xs text-slate-500">
                      {item.received_quantity} of {item.quantity} received &middot; {remaining} remaining
                    </p>
                  </div>
                  <div className="w-28">
                    <Label htmlFor={`qty-${item.product_id}`}>Receive qty</Label>
                    <Input
                      id={`qty-${item.product_id}`}
                      type="number"
                      min={0}
                      max={remaining}
                      value={quantities[item.product_id] ?? 0}
                      onChange={(event) =>
                        setQuantities((prev) => ({
                          ...prev,
                          [item.product_id]: Math.min(Number(event.target.value), remaining),
                        }))
                      }
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="button"
            onClick={handleSubmit}
            disabled={isSubmitting || pendingItems.length === 0}
          >
            {isSubmitting ? "Receiving…" : "Confirm Receipt"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
