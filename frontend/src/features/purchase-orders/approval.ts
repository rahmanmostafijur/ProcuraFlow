import type { ApprovalDocumentType, PurchaseOrder, QueueItem, User } from "@/api/types";

type ApprovalTarget = Pick<PurchaseOrder, "status"> & { creator: Pick<User, "id"> };
type Viewer = Pick<User, "id"> | null;
type PermissionCheck = (code: string) => boolean;

/** The approvals queue is worked out by the API for the signed-in user alone, so it is the truth about who may decide. */
export function isInQueue(
  queue: readonly QueueItem[] | undefined,
  documentType: ApprovalDocumentType,
  documentId: number,
): boolean {
  return queue?.some((item) => item.document_type === documentType && item.document_id === documentId) ?? false;
}

export function canDecidePurchaseOrder(
  po: Pick<PurchaseOrder, "id" | "status">,
  queue: readonly QueueItem[] | undefined,
): boolean {
  return po.status === "submitted" && isInQueue(queue, "purchase_order", po.id);
}

// Shown to a creator who holds the approve permission but is not in the queue for their own order.
export function needsAnotherApprover(
  po: ApprovalTarget & Pick<PurchaseOrder, "id">,
  user: Viewer,
  hasPermission: PermissionCheck,
  queue: readonly QueueItem[] | undefined,
): boolean {
  return (
    user !== null &&
    po.status === "submitted" &&
    hasPermission("po:approve") &&
    po.creator.id === user.id &&
    !isInQueue(queue, "purchase_order", po.id)
  );
}
