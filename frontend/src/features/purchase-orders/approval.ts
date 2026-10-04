import type { PurchaseOrder, User } from "@/api/types";

type ApprovalTarget = Pick<PurchaseOrder, "status"> & { creator: Pick<User, "id"> };
type Viewer = Pick<User, "id"> | null;
type PermissionCheck = (code: string) => boolean;

function isApprovalPending(po: ApprovalTarget, hasPermission: PermissionCheck): boolean {
  return po.status === "submitted" && hasPermission("po:approve");
}

// Mirrors the API's separation-of-duties rule: nobody approves a purchase order they created.
export function canApprovePurchaseOrder(po: ApprovalTarget, user: Viewer, hasPermission: PermissionCheck): boolean {
  return user !== null && isApprovalPending(po, hasPermission) && po.creator.id !== user.id;
}

export function needsAnotherApprover(po: ApprovalTarget, user: Viewer, hasPermission: PermissionCheck): boolean {
  return user !== null && isApprovalPending(po, hasPermission) && po.creator.id === user.id;
}
