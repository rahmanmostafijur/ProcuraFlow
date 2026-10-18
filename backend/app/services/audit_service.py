import enum
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


def to_json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, Mapping):
        return {key: to_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json_safe(item) for item in value]
    return value


def field_changes(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    """Describe the fields of ``after`` whose value differs from ``before`` as JSON-safe from/to pairs."""
    return {
        field: {"from": to_json_safe(before.get(field)), "to": to_json_safe(new_value)}
        for field, new_value in after.items()
        if before.get(field) != new_value
    }


def current_values(entity: object, fields: Iterable[str]) -> dict[str, Any]:
    return {field: getattr(entity, field) for field in fields}


async def record_audit_event(
    db: AsyncSession,
    *,
    user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    extra_data: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            extra_data=extra_data,
        )
    )
