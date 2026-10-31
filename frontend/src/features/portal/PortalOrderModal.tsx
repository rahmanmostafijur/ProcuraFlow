import { extractErrorMessage } from "@/api/client";
import { useAcknowledgeOrder, usePortalOrder } from "@/api/portal";
import { Button } from "@/components/ui/Button";
import { LoadingState } from "@/components/ui/LoadingState";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/toast-context";
import { formatCurrency, formatDateTime } from "@/lib/utils";

interface PortalOrderModalProps {
  orderId: number | null;
  onClose: () => void;
}

export function PortalOrderModal({ orderId, onClose }: PortalOrderModalProps) {
  const { showToast } = useToast();
  const { data: order, isLoading, isError } = usePortalOrder(orderId);
  const acknowledge = useAcknowledgeOrder();

  const confirm = async () => {
    if (orderId === null) return;
    try {
      await acknowledge.mutateAsync(orderId);
      showToast("Order acknowledged");
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  return (
    <Modal isOpen={orderId !== null} onClose={onClose} title={order ? `Order ${order.po_number}` : "Order"} size="lg">
      {isLoading && <LoadingState />}
      {isError && <p className="text-sm text-red-600">The order could not be loaded.</p>}
      {order && (
        <div className="space-y-4">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-slate-500">
              <tr>
                <th className="py-2 pr-3">Product</th>
                <th className="py-2 pr-3 text-right">Quantity</th>
                <th className="py-2 pr-3 text-right">Unit price</th>
                <th className="py-2 text-right">Total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {order.items.map((line) => (
                <tr key={line.product_id}>
                  <td className="py-2 pr-3">
                    {line.product_name} <span className="text-xs text-slate-500">{line.sku}</span>
                  </td>
                  <td className="py-2 pr-3 text-right">{line.quantity}</td>
                  <td className="py-2 pr-3 text-right">{formatCurrency(line.unit_price, order.currency_code)}</td>
                  <td className="py-2 text-right">{formatCurrency(line.line_total, order.currency_code)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-right text-sm font-semibold text-slate-900">
            Total {formatCurrency(order.grand_total, order.currency_code)}
          </p>
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm text-slate-600">
              {order.acknowledged_at
                ? `Acknowledged on ${formatDateTime(order.acknowledged_at)}`
                : "You have not acknowledged this order yet."}
            </p>
            {!order.acknowledged_at && (
              <Button disabled={acknowledge.isPending} onClick={() => void confirm()}>
                {acknowledge.isPending ? "Saving…" : "Acknowledge order"}
              </Button>
            )}
          </div>
        </div>
      )}
    </Modal>
  );
}
