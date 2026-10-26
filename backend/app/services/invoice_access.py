"""Who may see and change an invoice. A record someone may not see is reported as missing, never as forbidden."""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import has_permission
from app.models.approval import ApprovalStep
from app.models.enums import ApprovalDocumentType
from app.models.supplier_invoice import SupplierInvoice
from app.models.user import User
from app.services.approval_engine import with_permissions
from app.services.approval_queue_service import queue_for
from app.services.invoice_queries import get_invoice

READ_PERMISSION = "invoice:read"
APPROVE_PERMISSION = "invoice:approve"


async def can_view(db: AsyncSession, invoice: SupplierInvoice, viewer: User) -> bool:
    """People who read invoices, and approvers of the invoice's exception: named by one of its steps (by role, or by
    having decided it or decided it for someone), or able to decide it now as a delegate. Anyone who can be asked to
    decide can open it."""
    if has_permission(viewer, READ_PERMISSION):
        return True
    involved = await db.scalar(
        select(func.count())
        .select_from(ApprovalStep)
        .where(
            ApprovalStep.document_type == ApprovalDocumentType.INVOICE_EXCEPTION,
            ApprovalStep.document_id == invoice.id,
            (ApprovalStep.decided_by == viewer.id)
            | (ApprovalStep.on_behalf_of == viewer.id)
            | (ApprovalStep.approver_role_id == viewer.role_id),
        )
    )
    if involved:
        return True
    # Someone a delegation lets decide it right now.
    return any(
        item.document_type == ApprovalDocumentType.INVOICE_EXCEPTION and item.document_id == invoice.id
        for item in await queue_for(db, viewer)
    )


async def load_for(
    db: AsyncSession, invoice_id: int, actor: User, *, for_update: bool = False
) -> tuple[SupplierInvoice, User]:
    """The invoice (locked if asked) and the actor with their permissions in hand.

    Loading the invoice refreshes the people on it, which resets the role of the actor when they recorded or approved
    it, so the permissions are fetched again after the load.
    """
    invoice = await get_invoice(db, invoice_id, for_update=for_update)
    return invoice, await with_permissions(db, actor)


def not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")


def can_modify(invoice: SupplierInvoice, user: User) -> bool:
    """The person who recorded the invoice, or anyone who approves invoices."""
    return invoice.created_by == user.id or has_permission(user, APPROVE_PERMISSION)


def ensure_can_modify(invoice: SupplierInvoice, user: User) -> None:
    if not can_modify(invoice, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You can only change invoices that you recorded yourself."
        )


def require_approve_permission(user: User) -> None:
    if not has_permission(user, APPROVE_PERMISSION):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"You do not have the '{APPROVE_PERMISSION}' permission"
        )
