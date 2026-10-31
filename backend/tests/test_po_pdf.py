from datetime import date
from decimal import Decimal

from app.services.po_pdf import PdfLine, PdfOrder, PdfParty, render_po_pdf, tax_breakdown


def _line(sku: str, net: str, tax_name: str, percent: str) -> PdfLine:
    net_amount = Decimal(net)
    tax = (net_amount * Decimal(percent) / 100).quantize(Decimal("0.01"))
    return PdfLine(sku, f"Item {sku}", 2, net_amount / 2, tax_name, Decimal(percent), net_amount, tax, net_amount + tax)


def _order(lines: tuple[PdfLine, ...], **overrides: object) -> PdfOrder:
    values: dict[str, object] = {
        "po_number": "PO-0001",
        "issue_date": date(2026, 10, 31),
        "expected_delivery": date(2026, 11, 15),
        "currency_code": "EUR",
        "currency_symbol": "€",
        "minor_units": 2,
        "payment_terms_days": 30,
        "notes": "Deliver to <dock> 4 & call ahead",
        "company": PdfParty("Acme Ltd", ("1 Main St", "Berlin")),
        "supplier": PdfParty("Widgets GmbH", ("2 Side St",), tax_id="DE123"),
        "lines": lines,
        "subtotal": sum((line.net for line in lines), Decimal(0)),
        "tax_total": sum((line.tax for line in lines), Decimal(0)),
        "grand_total": sum((line.total for line in lines), Decimal(0)),
    }
    return PdfOrder(**(values | overrides))  # type: ignore[arg-type]


def test_tax_breakdown_has_one_row_per_rate() -> None:
    lines = (_line("A", "100.00", "VAT", "19"), _line("B", "50.00", "VAT", "7"), _line("C", "10.00", "VAT", "19"))
    rows = tax_breakdown(lines)
    assert rows == [
        ("VAT 7%", Decimal("50.00"), Decimal("3.50")),
        ("VAT 19%", Decimal("110.00"), Decimal("20.90")),
    ]


def test_renders_a_pdf_with_special_characters_in_free_text() -> None:
    pdf = render_po_pdf(_order((_line("A", "100.00", "VAT", "19"),)))
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


def test_a_corrupt_logo_does_not_stop_rendering() -> None:
    pdf = render_po_pdf(_order((_line("A", "100.00", "VAT", "19"),), logo=b"not an image", brand_color="nonsense"))
    assert pdf.startswith(b"%PDF")


def test_many_lines_paginate() -> None:
    lines = tuple(_line(f"S{i}", "10.00", "VAT", "19") for i in range(120))
    pdf = render_po_pdf(_order(lines))
    assert pdf.count(b"/Type /Page\n") + pdf.count(b"/Type /Page ") >= 2
