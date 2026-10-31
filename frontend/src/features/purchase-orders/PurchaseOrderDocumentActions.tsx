import { Download, Send } from "lucide-react";
import { useState } from "react";

import { extractErrorMessage } from "@/api/client";
import { fetchPurchaseOrderPdf, useSendPurchaseOrder } from "@/api/purchaseOrders";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/toast-context";
import { saveBlob } from "@/lib/download";

interface PurchaseOrderDocumentActionsProps {
  poId: number;
  poNumber: string;
  canSend: boolean;
}

/** Download as PDF for anyone who can view the order; emailing it to the supplier needs `canSend`. */
export function PurchaseOrderDocumentActions({ poId, poNumber, canSend }: PurchaseOrderDocumentActionsProps) {
  const { showToast } = useToast();
  const sendOrder = useSendPurchaseOrder();
  const [isDownloading, setDownloading] = useState(false);

  const download = async () => {
    setDownloading(true);
    try {
      saveBlob(await fetchPurchaseOrderPdf(poId), `${poNumber}.pdf`);
    } catch {
      // The error body of a blob request is a Blob, so the API's detail is not readable here.
      showToast("The PDF could not be downloaded. Please try again.", "error");
    } finally {
      setDownloading(false);
    }
  };

  const send = async () => {
    try {
      await sendOrder.mutateAsync(poId);
      showToast("Purchase order is on its way to the supplier");
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  return (
    <>
      <Button variant="secondary" disabled={isDownloading} onClick={() => void download()}>
        <Download className="h-4 w-4" /> {isDownloading ? "Preparing…" : "Download PDF"}
      </Button>
      {canSend && (
        <Button variant="secondary" disabled={sendOrder.isPending} onClick={() => void send()}>
          <Send className="h-4 w-4" /> {sendOrder.isPending ? "Sending…" : "Send to supplier"}
        </Button>
      )}
    </>
  );
}
