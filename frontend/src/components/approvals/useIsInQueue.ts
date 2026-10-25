import { useApprovalQueue } from "@/api/approvals";
import type { ApprovalDocumentType } from "@/api/types";
import { isInQueue } from "@/features/purchase-orders/approval";

// The API caps a page at 100 items; a document beyond that on a very long queue is still decided from /approvals.
const QUEUE_LOOKUP_SIZE = 100;

/** Whether the signed-in user may decide this document right now: the queue is the exact truth. */
export function useIsInQueue(documentType: ApprovalDocumentType, documentId: number | undefined): boolean {
  const { data } = useApprovalQueue(1, QUEUE_LOOKUP_SIZE);
  return documentId !== undefined && isInQueue(data?.items, documentType, documentId);
}
