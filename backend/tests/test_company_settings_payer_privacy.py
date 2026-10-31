from httpx import AsyncClient

from tests.fixture_types import AuthHeaders

URL = "/api/v1/company-settings"
PAYER_FIELDS = ("payer_iban", "payer_bic", "payer_routing_number", "payer_account_number", "ach_company_id")


async def test_payer_bank_details_are_shown_only_to_settings_managers(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    admin = await auth_headers("admin")
    saved = await client.patch(URL, json={"payer_iban": "NL91ABNA0417164300"}, headers=admin)
    assert saved.status_code == 200

    assert (await client.get(URL, headers=admin)).json()["payer_iban"] == "NL91ABNA0417164300"

    viewer = await auth_headers("viewer")
    seen = (await client.get(URL, headers=viewer)).json()
    assert {field: seen[field] for field in PAYER_FIELDS} == dict.fromkeys(PAYER_FIELDS)
    assert seen["company_name"]
