from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.product import Product
from app.models.supplier import Supplier
from app.storage.local import LocalStorage
from tests.fixture_types import AuthHeaders
from tests.sample_files import image_bytes, pdf_bytes

SETTINGS_URL = "/api/v1/company-settings"


async def test_any_signed_in_user_reads_the_defaults(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("viewer")

    response = await client.get(SETTINGS_URL, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["company_name"] == "ProcuraFlow"
    assert body["base_currency_code"] == "USD"
    assert body["po_number_prefix"] == "PO"
    assert body["invoice_tolerance_percent"] == "2.00"
    assert body["default_payment_terms_days"] == 30
    assert body["logo_url"] is None


async def test_full_settings_require_sign_in(client: AsyncClient) -> None:
    response = await client.get(SETTINGS_URL)

    assert response.status_code == 401


async def test_branding_is_public_and_limited(client: AsyncClient) -> None:
    response = await client.get(f"{SETTINGS_URL}/branding")

    assert response.status_code == 200
    assert response.json() == {"company_name": "ProcuraFlow", "brand_color": "#0F766E", "logo_url": None}


async def test_admin_updates_settings_and_the_change_is_audited(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession
) -> None:
    headers = await auth_headers("admin")
    payload = {
        "company_name": "Northbeam Instruments",
        "legal_name": "Northbeam Instruments Inc.",
        "country_code": "us",
        "tax_id": "EIN 12-3456789",
        "brand_color": "#1d4ed8",
        "date_format": "DD/MM/YYYY",
        "timezone": "Europe/Berlin",
        "po_number_prefix": "nbi",
        "invoice_tolerance_percent": "5.5",
        "default_payment_terms_days": 45,
        "fiscal_year_start_month": 4,
    }

    response = await client.patch(SETTINGS_URL, json=payload, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["company_name"] == "Northbeam Instruments"
    assert body["country_code"] == "US"
    assert body["brand_color"] == "#1D4ED8"
    assert body["po_number_prefix"] == "NBI"
    assert body["invoice_tolerance_percent"] == "5.50"
    branding = (await client.get(f"{SETTINGS_URL}/branding")).json()
    assert branding["company_name"] == "Northbeam Instruments"
    audit = await db_session.scalar(select(AuditLog).where(AuditLog.action == "company_settings_updated"))
    assert audit is not None
    assert audit.extra_data is not None
    assert audit.extra_data["changes"]["company_name"] == {"from": "ProcuraFlow", "to": "Northbeam Instruments"}


async def test_blank_optional_fields_are_stored_as_empty(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("admin")
    await client.patch(SETTINGS_URL, json={"legal_name": "Old Name LLC"}, headers=headers)

    response = await client.patch(SETTINGS_URL, json={"legal_name": "   "}, headers=headers)

    assert response.json()["legal_name"] is None


@pytest.mark.parametrize("role", ["viewer", "procurement_manager", "purchasing_officer", "warehouse_manager"])
async def test_only_settings_managers_can_change_settings(
    client: AsyncClient, auth_headers: AuthHeaders, role: str
) -> None:
    headers = await auth_headers(role)

    response = await client.patch(SETTINGS_URL, json={"company_name": "Hijacked"}, headers=headers)

    assert response.status_code == 403


@pytest.mark.parametrize(
    "payload",
    [
        {"brand_color": "teal"},
        {"brand_color": "#12345"},
        {"timezone": "Mars/Olympus_Mons"},
        {"base_currency_code": "US"},
        {"po_number_prefix": "PO-2026"},
        {"po_number_prefix": "WAYTOOLONGPREFIX"},
        {"invoice_tolerance_percent": "100.01"},
        {"invoice_tolerance_percent": "-1"},
        {"invoice_tolerance_percent": "1.234"},
        {"fiscal_year_start_month": 13},
        {"default_payment_terms_days": -1},
        {"date_format": "YYYY/DD/MM"},
        {"country_code": "USA"},
        {"contact_email": "not-an-email"},
        {"company_name": ""},
        {"company_name": None},
        {"timezone": None},
    ],
)
async def test_invalid_settings_are_rejected(
    client: AsyncClient, auth_headers: AuthHeaders, payload: dict[str, Any]
) -> None:
    headers = await auth_headers("admin")

    response = await client.patch(SETTINGS_URL, json=payload, headers=headers)

    assert response.status_code == 422


async def test_new_purchase_orders_use_the_configured_prefix(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    admin = await auth_headers("admin")
    await client.patch(SETTINGS_URL, json={"po_number_prefix": "NBI"}, headers=admin)

    response = await client.post(
        "/api/v1/purchase-orders",
        json={"supplier_id": supplier.id, "items": [{"product_id": product.id, "quantity": 1, "unit_price": "5.00"}]},
        headers=admin,
    )

    assert response.status_code == 201
    assert response.json()["po_number"].startswith("NBI-")


async def _upload_logo(client: AsyncClient, headers: dict[str, str], data: bytes, name: str = "logo.png") -> Any:
    return await client.put(f"{SETTINGS_URL}/logo", files={"file": (name, data, "image/png")}, headers=headers)


@pytest.mark.parametrize("image_format", ["PNG", "JPEG"])
async def test_admin_uploads_a_logo_that_anyone_can_fetch(
    client: AsyncClient, auth_headers: AuthHeaders, image_format: str
) -> None:
    headers = await auth_headers("admin")
    data = image_bytes(image_format)

    response = await _upload_logo(client, headers, data)

    assert response.status_code == 200
    logo_url = response.json()["logo_url"]
    assert logo_url.startswith("/company-settings/logo?v=")
    logo = await client.get(f"/api/v1{logo_url}")
    assert logo.status_code == 200
    assert logo.content == data
    assert logo.headers["content-type"] == ("image/png" if image_format == "PNG" else "image/jpeg")
    assert logo.headers["x-content-type-options"] == "nosniff"


async def test_replacing_the_logo_deletes_the_old_file(
    client: AsyncClient, auth_headers: AuthHeaders, storage: LocalStorage, tmp_path: Any
) -> None:
    headers = await auth_headers("admin")
    await _upload_logo(client, headers, image_bytes("PNG"))
    await _upload_logo(client, headers, image_bytes("PNG", size=(16, 16)))

    stored_files = list((tmp_path / "uploads" / "logos").iterdir())

    assert len(stored_files) == 1


async def test_logo_must_really_be_an_image(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("admin")

    disguised = await _upload_logo(client, headers, b"<script>alert(1)</script>", name="logo.png")
    pdf = await _upload_logo(client, headers, pdf_bytes(), name="logo.png")
    gif = await _upload_logo(client, headers, image_bytes("GIF"), name="logo.gif")

    assert disguised.status_code == 415
    assert pdf.status_code == 415
    assert gif.status_code == 415


async def test_oversized_logo_is_refused(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("admin")
    oversized = image_bytes("PNG") + b"\0" * (1024 * 1024)

    response = await _upload_logo(client, headers, oversized)

    assert response.status_code == 413


async def test_empty_logo_upload_is_refused(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("admin")

    response = await _upload_logo(client, headers, b"")

    assert response.status_code == 422


async def test_non_admin_cannot_upload_or_remove_the_logo(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("procurement_manager")

    upload = await _upload_logo(client, headers, image_bytes("PNG"))
    removal = await client.delete(f"{SETTINGS_URL}/logo", headers=headers)

    assert upload.status_code == 403
    assert removal.status_code == 403


async def test_removing_the_logo(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("admin")
    await _upload_logo(client, headers, image_bytes("PNG"))

    response = await client.delete(f"{SETTINGS_URL}/logo", headers=headers)

    assert response.status_code == 200
    assert response.json()["logo_url"] is None
    assert (await client.get(f"{SETTINGS_URL}/logo")).status_code == 404


async def test_invoice_matching_defaults_to_three_way(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("viewer")

    body = (await client.get(SETTINGS_URL, headers=headers)).json()

    assert body["invoice_matching"] == "three_way"


async def test_admin_switches_invoice_matching_and_it_is_audited(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession
) -> None:
    headers = await auth_headers("admin")

    response = await client.patch(SETTINGS_URL, json={"invoice_matching": "two_way"}, headers=headers)

    assert response.status_code == 200
    assert response.json()["invoice_matching"] == "two_way"
    audit = await db_session.scalar(select(AuditLog).where(AuditLog.action == "company_settings_updated"))
    assert audit is not None
    assert audit.extra_data is not None
    assert audit.extra_data["changes"]["invoice_matching"] == {"from": "three_way", "to": "two_way"}


@pytest.mark.parametrize("value", ["four_way", "THREE_WAY", "", 3])
async def test_an_unknown_invoice_matching_mode_is_refused(
    client: AsyncClient, auth_headers: AuthHeaders, value: Any
) -> None:
    headers = await auth_headers("admin")

    response = await client.patch(SETTINGS_URL, json={"invoice_matching": value}, headers=headers)

    assert response.status_code == 422


async def test_invoice_matching_cannot_be_cleared(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("admin")

    response = await client.patch(SETTINGS_URL, json={"invoice_matching": None}, headers=headers)

    assert response.status_code == 422
    assert "invoice_matching" in response.text


async def test_only_settings_managers_change_invoice_matching(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("finance")

    response = await client.patch(SETTINGS_URL, json={"invoice_matching": "two_way"}, headers=headers)

    assert response.status_code == 403
