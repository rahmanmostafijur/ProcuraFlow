from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.core.deps import CurrentUser, DbSession, require_permission
from app.models.approval import ApprovalDelegation, ApprovalLimit, ApprovalRule
from app.models.enums import ApprovalDocumentType
from app.models.user import User
from app.schemas.approval import (
    ApprovalLimitRead,
    ApprovalLimitWrite,
    ApprovalRuleCreate,
    ApprovalRuleRead,
    ApprovalRuleUpdate,
    DelegationCreate,
    DelegationRead,
)
from app.services import approval_people_service, approval_rules_service

router = APIRouter(tags=["approval-settings"])

RequireApprovalManage = Annotated[User, Depends(require_permission("approval:manage"))]


# --- rules (the people who run approvals see and change them) -----------------------------------------------------


@router.get("/approval-rules", response_model=list[ApprovalRuleRead])
async def list_rules(
    db: DbSession, _: RequireApprovalManage, document_type: ApprovalDocumentType | None = None
) -> list[ApprovalRule]:
    return await approval_rules_service.list_rules(db, document_type)


@router.post("/approval-rules", response_model=ApprovalRuleRead, status_code=status.HTTP_201_CREATED)
async def create_rule(payload: ApprovalRuleCreate, db: DbSession, user: RequireApprovalManage) -> ApprovalRule:
    return await approval_rules_service.create_rule(db, payload, user)


@router.patch("/approval-rules/{rule_id}", response_model=ApprovalRuleRead)
async def update_rule(
    rule_id: int, payload: ApprovalRuleUpdate, db: DbSession, user: RequireApprovalManage
) -> ApprovalRule:
    return await approval_rules_service.update_rule(db, rule_id, payload, user)


@router.delete("/approval-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(rule_id: int, db: DbSession, user: RequireApprovalManage) -> Response:
    await approval_rules_service.delete_rule(db, rule_id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- limits -------------------------------------------------------------------------------------------------------


@router.get("/approval-limits", response_model=list[ApprovalLimitRead])
async def list_limits(db: DbSession, user: CurrentUser) -> list[ApprovalLimit]:
    """Everyone's limits for those who manage approvals; anyone else sees only their own."""
    return await approval_people_service.list_limits(db, user)


@router.put("/approval-limits", response_model=ApprovalLimitRead)
async def set_limit(payload: ApprovalLimitWrite, db: DbSession, user: RequireApprovalManage) -> ApprovalLimit:
    return await approval_people_service.set_limit(db, payload, user)


@router.delete("/approval-limits/{limit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_limit(limit_id: int, db: DbSession, user: RequireApprovalManage) -> Response:
    await approval_people_service.delete_limit(db, limit_id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- delegation (anyone can hand their own approvals to someone while away) ---------------------------------------


@router.get("/approval-delegations", response_model=list[DelegationRead])
async def list_delegations(db: DbSession, user: CurrentUser) -> list[ApprovalDelegation]:
    """Those the caller gave or received; everything for people who manage approvals."""
    return await approval_people_service.list_delegations(db, user)


@router.post("/approval-delegations", response_model=DelegationRead, status_code=status.HTTP_201_CREATED)
async def create_delegation(payload: DelegationCreate, db: DbSession, user: CurrentUser) -> ApprovalDelegation:
    return await approval_people_service.create_delegation(db, payload, user)


@router.post("/approval-delegations/{delegation_id}/revoke", response_model=DelegationRead)
async def revoke_delegation(delegation_id: int, db: DbSession, user: CurrentUser) -> ApprovalDelegation:
    return await approval_people_service.revoke_delegation(db, delegation_id, user)
