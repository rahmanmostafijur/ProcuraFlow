import json
from datetime import date, datetime, timezone
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.models.audit import AuditLog
from app.models.enums import POStatus
from app.models.user import User
from app.services.audit_service import field_changes


async def _audit_events(db_session: AsyncSession, action: str, entity_id: int) -> list[AuditLog]:
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == action, AuditLog.entity_id == entity_id).order_by(AuditLog.id)
    )
    return list(result.scalars().all())


async def _single_event(db_session: AsyncSession, action: str, entity_id: int) -> AuditLog:
    events = await _audit_events(db_session, action, entity_id)
    assert len(events) == 1
    return events[0]


async def _create_draft_po(client: AsyncClient, headers: dict, supplier, product) -> dict:
    response = await client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier.id,
            "items": [{"product_id": product.id, "quantity": 10, "unit_price": "10.00"}],
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


async def test_creating_a_category_records_an_audit_event(
    client: AsyncClient, auth_headers, db_session: AsyncSession
):
    headers = await auth_headers("admin")
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()

    response = await client.post("/api/v1/categories", json={"name": "Fasteners"}, headers=headers)

    assert response.status_code == 201
    category_id = response.json()["id"]
    events = await _audit_events(db_session, "category_created", category_id)
    assert len(events) == 1
    assert events[0].entity_type == "category"
    assert events[0].user_id == me["id"]


def test_field_changes_lists_only_changed_fields_as_json_safe_values():
    before = {
        "name": "Widget",
        "cost": Decimal("10.00"),
        "expected_delivery_date": date(2026, 1, 31),
        "approved_at": datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        "status": POStatus.DRAFT,
        "minimum_stock": 5,
    }
    after = {
        "name": "Widget",
        "cost": Decimal("12.5"),
        "expected_delivery_date": date(2026, 2, 28),
        "approved_at": None,
        "status": POStatus.SUBMITTED,
        "minimum_stock": 5,
    }

    changes = field_changes(before, after)

    assert changes == {
        "cost": {"from": "10.00", "to": "12.5"},
        "expected_delivery_date": {"from": "2026-01-31", "to": "2026-02-28"},
        "approved_at": {"from": "2026-01-02T03:04:05+00:00", "to": None},
        "status": {"from": "draft", "to": "submitted"},
    }
    json.dumps(changes)


async def test_product_update_records_changed_fields(
    client: AsyncClient, auth_headers, product, db_session: AsyncSession
):
    headers = await auth_headers("admin")

    response = await client.patch(
        f"/api/v1/products/{product.id}",
        json={"name": "Better Widget", "cost": "12.50", "minimum_stock": product.minimum_stock},
        headers=headers,
    )

    assert response.status_code == 200
    event = await _single_event(db_session, "product_updated", product.id)
    assert event.extra_data == {
        "changes": {
            "name": {"from": "Test Widget", "to": "Better Widget"},
            "cost": {"from": "10.00", "to": "12.50"},
        }
    }


async def test_no_op_update_records_an_event_with_no_changes(
    client: AsyncClient, auth_headers, product, db_session: AsyncSession
):
    headers = await auth_headers("admin")

    response = await client.patch(
        f"/api/v1/products/{product.id}", json={"name": product.name, "cost": "10.0"}, headers=headers
    )

    assert response.status_code == 200
    event = await _single_event(db_session, "product_updated", product.id)
    assert event.extra_data == {"changes": {}}


async def test_supplier_update_records_changed_fields(
    client: AsyncClient, auth_headers, supplier, db_session: AsyncSession
):
    headers = await auth_headers("admin")

    response = await client.patch(
        f"/api/v1/suppliers/{supplier.id}",
        json={"contact_name": "Jane Doe", "is_active": False, "name": supplier.name},
        headers=headers,
    )

    assert response.status_code == 200
    event = await _single_event(db_session, "supplier_updated", supplier.id)
    assert event.extra_data == {
        "changes": {
            "contact_name": {"from": None, "to": "Jane Doe"},
            "is_active": {"from": True, "to": False},
        }
    }


async def test_user_update_records_changes_and_redacts_the_password(
    client: AsyncClient, auth_headers, make_user, roles, db_session: AsyncSession
):
    headers = await auth_headers("admin")
    target = await make_user("target@example.com", "viewer")
    old_hash = target.hashed_password
    new_password = "BrandNewSecret99!"

    response = await client.patch(
        f"/api/v1/users/{target.id}",
        json={"full_name": "Renamed User", "role_id": roles["purchasing_officer"].id, "password": new_password},
        headers=headers,
    )

    assert response.status_code == 200
    event = await _single_event(db_session, "user_updated", target.id)
    assert event.extra_data == {
        "changes": {
            "full_name": {"from": "Viewer User", "to": "Renamed User"},
            "role_id": {"from": roles["viewer"].id, "to": roles["purchasing_officer"].id},
            "password": "changed",
        }
    }
    # Selecting the column reads the persisted row directly. (expire_all() here used to expire `target`
    # and `event`, and touching their attributes afterwards lazy-loaded outside the async context.)
    new_hash = await db_session.scalar(select(User.hashed_password).where(User.id == target.id))
    assert new_hash != old_hash
    assert verify_password(new_password, new_hash)
    serialized = json.dumps(event.extra_data)
    assert new_password not in serialized
    assert new_hash not in serialized
    assert old_hash not in serialized


async def test_user_update_without_a_password_does_not_mention_it(
    client: AsyncClient, auth_headers, make_user, db_session: AsyncSession
):
    headers = await auth_headers("admin")
    target = await make_user("target@example.com", "viewer")

    response = await client.patch(f"/api/v1/users/{target.id}", json={"is_active": False}, headers=headers)

    assert response.status_code == 200
    event = await _single_event(db_session, "user_updated", target.id)
    assert event.extra_data == {"changes": {"is_active": {"from": True, "to": False}}}


async def test_purchase_order_update_records_field_and_line_item_changes(
    client: AsyncClient, auth_headers, supplier, product, db_session: AsyncSession
):
    headers = await auth_headers("procurement_manager")
    po = await _create_draft_po(client, headers, supplier, product)

    response = await client.patch(
        f"/api/v1/purchase-orders/{po['id']}",
        json={
            "notes": "Rush order",
            "expected_delivery_date": "2026-11-30",
            "items": [{"product_id": product.id, "quantity": 4, "unit_price": "9.50"}],
        },
        headers=headers,
    )

    assert response.status_code == 200
    event = await _single_event(db_session, "po_updated", po["id"])
    assert event.extra_data == {
        "changes": {
            "notes": {"from": None, "to": "Rush order"},
            "expected_delivery_date": {"from": None, "to": "2026-11-30"},
            "items": {
                "from": [{"product_id": product.id, "quantity": 10, "unit_price": "10.00"}],
                "to": [{"product_id": product.id, "quantity": 4, "unit_price": "9.50"}],
            },
        }
    }


async def test_purchase_order_update_with_identical_items_records_no_item_change(
    client: AsyncClient, auth_headers, supplier, product, db_session: AsyncSession
):
    headers = await auth_headers("procurement_manager")
    po = await _create_draft_po(client, headers, supplier, product)

    response = await client.patch(
        f"/api/v1/purchase-orders/{po['id']}",
        json={"notes": "Keep lines", "items": [{"product_id": product.id, "quantity": 10, "unit_price": "10"}]},
        headers=headers,
    )

    assert response.status_code == 200
    event = await _single_event(db_session, "po_updated", po["id"])
    assert event.extra_data == {"changes": {"notes": {"from": None, "to": "Keep lines"}}}
