"""The fictional company's reference data: suppliers, products and cost centres. Plain data, no behaviour.

Every name here is invented. Prices are in the supplier's own currency; amounts the company reports in are
converted by the application at the exchange rates the seed loads.
"""

from dataclasses import dataclass
from decimal import Decimal

COMPANY_NAME = "Northbridge Trading Co."
BASE_CURRENCY = "USD"
TIMEZONE = "America/New_York"


@dataclass(frozen=True)
class SupplierSpec:
    name: str
    short: str  # invoice number prefix
    contact_name: str
    email: str
    phone: str
    address: str
    country_code: str
    currency_code: str
    payment_terms_days: int
    tax_id: str
    cost_centre: str
    # Tax rate applied to this supplier's order lines (a key of TAX_RATES), None for none.
    tax: str | None = None
    # IBAN of a supplier paid by SEPA transfer, None when no bank details are kept.
    iban: str | None = None
    bic: str | None = None


@dataclass(frozen=True)
class ProductSpec:
    sku: str
    name: str
    category: str
    unit: str
    supplier: str
    price: Decimal
    minimum_stock: int
    # Stock the ledger starts with; the seed later books what the year's receipts and issues leave.
    opening_stock: int
    # The stock level the product should end on relative to its minimum (below 1 means a low-stock alert).
    stock_ratio: Decimal


@dataclass(frozen=True)
class CostCentreSpec:
    code: str
    name: str
    manager_key: str
    # Share of the budget used (spent plus committed) once the seed has finished: some healthy, some near, one over.
    target_percent: int


# key -> (name, percentage, region)
TAX_RATES: dict[str, tuple[str, str, str]] = {
    "DE": ("VAT 19% (Germany)", "19", "DE"),
    "FR": ("VAT 20% (France)", "20", "FR"),
    "NL": ("VAT 21% (Netherlands)", "21", "NL"),
    "GB": ("VAT 20% (United Kingdom)", "20", "GB"),
}

SUPPLIERS: tuple[SupplierSpec, ...] = (
    SupplierSpec(
        "Prairie Office Supply Co.",
        "POS",
        "Dana Whitfield",
        "orders@prairieoffice.example.com",
        "+1 312 555 0141",
        "410 W Lake Street, Chicago, IL 60606",
        "US",
        "USD",
        30,
        "US-36-0011422",
        "ADM",
    ),
    SupplierSpec(
        "Lakeshore Packaging Inc.",
        "LPI",
        "Omar Haddad",
        "sales@lakeshorepack.example.com",
        "+1 414 555 0178",
        "2200 Harbor Drive, Milwaukee, WI 53202",
        "US",
        "USD",
        45,
        "US-39-0087120",
        "WH",
    ),
    SupplierSpec(
        "Summit Industrial Parts LLC",
        "SIP",
        "Rita Alvarez",
        "accounts@summitparts.example.com",
        "+1 216 555 0119",
        "75 Foundry Road, Cleveland, OH 44113",
        "US",
        "USD",
        30,
        "US-34-0052981",
        "OPS",
    ),
    SupplierSpec(
        "Rheinwerk Elektronik GmbH",
        "REG",
        "Katrin Vogel",
        "vertrieb@rheinwerk-elektronik.example.com",
        "+49 211 555 0132",
        "Kaiserswerther Strasse 88, 40474 Duesseldorf",
        "DE",
        "EUR",
        30,
        "DE812345678",
        "IT",
        "DE",
        "DE89370400440532013000",
        "COBADEFFXXX",
    ),
    SupplierSpec(
        "Atelier Lumiere SARL",
        "ALS",
        "Claire Duval",
        "commandes@atelier-lumiere.example.com",
        "+33 1 55 55 01 24",
        "18 Rue des Fabriques, 69002 Lyon",
        "FR",
        "EUR",
        45,
        "FR40303265612",
        "FAC",
        "FR",
        "FR1420041010050500013M02606",
        "BNPAFRPPXXX",
    ),
    SupplierSpec(
        "Nordhaven Logistics BV",
        "NHL",
        "Pieter de Vries",
        "orders@nordhaven-logistics.example.com",
        "+31 10 555 0187",
        "Waalhaven Zuidzijde 12, 3089 JH Rotterdam",
        "NL",
        "EUR",
        30,
        "NL853294710B01",
        "WH",
        "NL",
    ),
    SupplierSpec(
        "Thames Stationery Ltd",
        "TSL",
        "Hannah Boyd",
        "sales@thamesstationery.example.com",
        "+44 20 5550 0166",
        "9 Wharf Lane, London SE1 9PG",
        "GB",
        "GBP",
        30,
        "GB123456789",
        "ADM",
        "GB",
    ),
    SupplierSpec(
        "Brightwell Components Ltd",
        "BWC",
        "Samuel Price",
        "accounts@brightwell-components.example.com",
        "+44 121 555 0103",
        "Unit 4, Canal Works, Birmingham B16 8QX",
        "GB",
        "GBP",
        60,
        "GB987654321",
        "ENG",
        "GB",
    ),
)
SUPPLIERS_BY_NAME = {supplier.name: supplier for supplier in SUPPLIERS}


def _product(  # noqa: PLR0913, PLR0917 - one positional row per product keeps the table readable
    sku: str, name: str, category: str, unit: str, supplier: str, price: str, minimum: int, opening: int, ratio: str
) -> ProductSpec:
    return ProductSpec(sku, name, category, unit, supplier, Decimal(price), minimum, opening, Decimal(ratio))


PRODUCTS: tuple[ProductSpec, ...] = (
    _product(
        "OFF-1001",
        "A4 copy paper, 5 reams",
        "Office Supplies",
        "box",
        "Prairie Office Supply Co.",
        "24.50",
        60,
        180,
        "1.8",
    ),
    _product(
        "OFF-1002",
        "Ballpoint pens, box of 50",
        "Office Supplies",
        "box",
        "Prairie Office Supply Co.",
        "8.25",
        30,
        90,
        "2.2",
    ),
    _product(
        "OFF-1003", "Heavy-duty stapler", "Office Supplies", "unit", "Prairie Office Supply Co.", "14.90", 10, 24, "0.5"
    ),
    _product(
        "PKG-2001", "Corrugated box, medium", "Packaging", "unit", "Lakeshore Packaging Inc.", "0.85", 500, 2400, "2.0"
    ),
    _product("PKG-2002", "Stretch wrap roll", "Packaging", "roll", "Lakeshore Packaging Inc.", "12.40", 40, 160, "1.6"),
    _product(
        "PKG-2003", "Packing tape, 6 rolls", "Packaging", "pack", "Lakeshore Packaging Inc.", "9.75", 80, 260, "1.4"
    ),
    _product(
        "IND-3001",
        "Hydraulic pump 2.2 kW",
        "Industrial Parts",
        "unit",
        "Summit Industrial Parts LLC",
        "486.00",
        5,
        14,
        "1.5",
    ),
    _product(
        "IND-3002",
        "Steel bracket, 120 mm",
        "Industrial Parts",
        "unit",
        "Summit Industrial Parts LLC",
        "3.10",
        400,
        1500,
        "2.4",
    ),
    _product(
        "IND-3003",
        "Safety gloves, pair",
        "Industrial Parts",
        "pair",
        "Summit Industrial Parts LLC",
        "4.25",
        100,
        340,
        "0.6",
    ),
    _product(
        "ELC-4001", "USB-C dock, 8 ports", "Electronics", "unit", "Rheinwerk Elektronik GmbH", "74.90", 15, 40, "1.7"
    ),
    _product(
        "ELC-4002", "Wireless keyboard", "Electronics", "unit", "Rheinwerk Elektronik GmbH", "29.50", 25, 70, "1.3"
    ),
    _product(
        "ELC-4003", "27-inch monitor", "Electronics", "unit", "Rheinwerk Elektronik GmbH", "189.00", 10, 26, "1.9"
    ),
    _product("FAC-5001", "LED panel light 60x60", "Facilities", "unit", "Atelier Lumiere SARL", "42.00", 20, 60, "1.5"),
    _product("FAC-5002", "Desk lamp", "Facilities", "unit", "Atelier Lumiere SARL", "23.50", 20, 55, "0.7"),
    _product("FAC-5003", "Ergonomic chair", "Facilities", "unit", "Atelier Lumiere SARL", "214.00", 8, 20, "1.8"),
    _product("LOG-6001", "EUR pallet", "Logistics", "unit", "Nordhaven Logistics BV", "11.80", 100, 420, "2.5"),
    _product("LOG-6002", "Pallet strapping kit", "Logistics", "kit", "Nordhaven Logistics BV", "18.60", 30, 90, "1.5"),
    _product(
        "LOG-6003", "Warehouse label roll", "Logistics", "roll", "Nordhaven Logistics BV", "6.40", 150, 500, "1.2"
    ),
    _product(
        "STA-7001",
        "Notebook A5, pack of 10",
        "Office Supplies",
        "pack",
        "Thames Stationery Ltd",
        "11.20",
        40,
        110,
        "1.6",
    ),
    _product(
        "STA-7002", "Whiteboard markers, 12", "Office Supplies", "pack", "Thames Stationery Ltd", "7.85", 30, 85, "2.0"
    ),
    _product(
        "STA-7003", "Lever arch files, 10", "Office Supplies", "pack", "Thames Stationery Ltd", "13.50", 25, 70, "1.3"
    ),
    _product(
        "CMP-8001", "Servo motor 400 W", "Components", "unit", "Brightwell Components Ltd", "168.00", 6, 16, "1.4"
    ),
    _product(
        "CMP-8002", "Control cable, 5 m", "Components", "unit", "Brightwell Components Ltd", "9.20", 60, 190, "0.4"
    ),
    _product("CMP-8003", "Pneumatic valve", "Components", "unit", "Brightwell Components Ltd", "38.50", 15, 44, "1.6"),
)

COST_CENTRES: tuple[CostCentreSpec, ...] = (
    CostCentreSpec("OPS", "Operations", "department_manager", 62),
    CostCentreSpec("WH", "Warehouse and logistics", "warehouse_manager", 88),
    CostCentreSpec("IT", "IT and workplace", "procurement_manager", 112),
    CostCentreSpec("FAC", "Facilities", "department_manager", 45),
    CostCentreSpec("ENG", "Engineering", "procurement_manager", 93),
    CostCentreSpec("ADM", "Administration", "department_manager", 55),
)

CATEGORIES = (
    "Office Supplies",
    "Packaging",
    "Industrial Parts",
    "Electronics",
    "Facilities",
    "Logistics",
    "Components",
)

# Units of a currency in the company's base currency, over the year (a gentle drift around these values).
EXCHANGE_RATES: dict[str, Decimal] = {"EUR": Decimal("1.0850"), "GBP": Decimal("1.2650")}
