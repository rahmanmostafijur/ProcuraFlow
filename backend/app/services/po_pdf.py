"""Branded purchase order PDF. Amounts are the stored per-line values, never recomputed here."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.money import trim_money

DEFAULT_BRAND_COLOR = "#1f4e79"
LOGO_MAX_WIDTH = 45 * mm
LOGO_MAX_HEIGHT = 18 * mm


@dataclass(frozen=True)
class PdfLine:
    sku: str
    description: str
    quantity: int
    unit_price: Decimal
    tax_name: str
    tax_percent: Decimal
    net: Decimal
    tax: Decimal
    total: Decimal


@dataclass(frozen=True)
class PdfParty:
    name: str
    address_lines: tuple[str, ...]
    tax_id: str | None = None


@dataclass(frozen=True)
class PdfOrder:
    po_number: str
    issue_date: date
    expected_delivery: date | None
    currency_code: str
    currency_symbol: str
    minor_units: int
    payment_terms_days: int | None
    notes: str | None
    company: PdfParty
    supplier: PdfParty
    lines: tuple[PdfLine, ...]
    subtotal: Decimal
    tax_total: Decimal
    grand_total: Decimal
    brand_color: str = DEFAULT_BRAND_COLOR
    logo: bytes | None = None


def _money(order: PdfOrder, value: Decimal) -> str:
    text = f"{value:,.{order.minor_units}f}"
    return f"{order.currency_code} {text}"


def _percent(value: Decimal) -> str:
    return f"{value.normalize():f}%"


def tax_breakdown(lines: tuple[PdfLine, ...]) -> list[tuple[str, Decimal, Decimal]]:
    """Net and tax per tax name and rate, so a mixed-rate order shows each rate on its own row."""
    buckets: dict[tuple[str, Decimal], list[Decimal]] = defaultdict(lambda: [Decimal(0), Decimal(0)])
    for line in lines:
        bucket = buckets[(line.tax_name, line.tax_percent)]
        bucket[0] += line.net
        bucket[1] += line.tax
    return [
        (f"{name} {_percent(percent)}" if percent else name, net, tax)
        for (name, percent), (net, tax) in sorted(buckets.items(), key=lambda item: (item[0][0], item[0][1]))
    ]


def _paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text).replace("\n", "<br/>"), style)


def _party_block(title: str, party: PdfParty, styles: dict[str, ParagraphStyle]) -> list[Paragraph]:
    block = [Paragraph(title, styles["label"]), _paragraph(party.name, styles["bold"])]
    block.extend(_paragraph(line, styles["body"]) for line in party.address_lines if line)
    if party.tax_id:
        block.append(_paragraph(f"Tax ID: {party.tax_id}", styles["body"]))
    return block


def _styles(brand: colors.Color) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()["BodyText"]
    return {
        "body": ParagraphStyle("body", parent=base, fontSize=9, leading=12),
        "bold": ParagraphStyle("bold", parent=base, fontName="Helvetica-Bold", fontSize=10, leading=13),
        "label": ParagraphStyle("label", parent=base, fontSize=8, textColor=colors.grey, leading=10),
        "title": ParagraphStyle("title", parent=base, fontName="Helvetica-Bold", fontSize=20, textColor=brand),
        "right": ParagraphStyle("right", parent=base, fontSize=9, alignment=2),
    }


def _parse_color(value: str) -> colors.Color:
    try:
        return colors.HexColor(value)
    except ValueError:
        return colors.HexColor(DEFAULT_BRAND_COLOR)


def _logo(data: bytes) -> Image | None:
    try:
        image = Image(BytesIO(data))
        scale = min(LOGO_MAX_WIDTH / image.drawWidth, LOGO_MAX_HEIGHT / image.drawHeight, 1)
        image.drawWidth *= scale
        image.drawHeight *= scale
    except Exception:
        return None
    return image


def _header(order: PdfOrder, styles: dict[str, ParagraphStyle]) -> Table:
    logo = _logo(order.logo) if order.logo else None
    left: list[object] = [logo] if logo else [_paragraph(order.company.name, styles["title"])]
    details = [
        _paragraph("PURCHASE ORDER", styles["bold"]),
        _paragraph(order.po_number, styles["right"]),
        _paragraph(f"Date: {order.issue_date.isoformat()}", styles["right"]),
    ]
    if order.expected_delivery:
        details.append(_paragraph(f"Delivery: {order.expected_delivery.isoformat()}", styles["right"]))
    table = Table([[left, details]], colWidths=[95 * mm, 80 * mm])
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return table


def _lines_table(order: PdfOrder, brand: colors.Color, styles: dict[str, ParagraphStyle]) -> Table:
    rows: list[list[object]] = [["SKU", "Description", "Qty", "Unit price", "Tax", "Total"]]
    for line in order.lines:
        rows.append(
            [
                line.sku,
                _paragraph(line.description, styles["body"]),
                str(line.quantity),
                f"{trim_money(line.unit_price):,}",
                _percent(line.tax_percent) if line.tax_percent else "-",
                f"{line.total:,.{order.minor_units}f}",
            ]
        )
    table = Table(rows, colWidths=[24 * mm, 63 * mm, 15 * mm, 25 * mm, 18 * mm, 30 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), brand),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ]
        )
    )
    return table


def _totals_table(order: PdfOrder, styles: dict[str, ParagraphStyle]) -> Table:
    rows: list[list[object]] = [["Tax breakdown", "Net", "Tax"]]
    rows.extend([label, _money(order, net), _money(order, tax)] for label, net, tax in tax_breakdown(order.lines))
    rows.append(["Subtotal", "", _money(order, order.subtotal)])
    rows.append(["Tax", "", _money(order, order.tax_total)])
    rows.append(["Total", "", _money(order, order.grand_total)])
    table = Table(rows, colWidths=[60 * mm, 45 * mm, 45 * mm], hAlign="RIGHT")
    table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("LINEABOVE", (0, -3), (-1, -3), 0.5, colors.grey),
                ("LINEABOVE", (0, -1), (-1, -1), 0.5, colors.black),
            ]
        )
    )
    return table


def render_po_pdf(order: PdfOrder) -> bytes:
    brand = _parse_color(order.brand_color)
    styles = _styles(brand)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Purchase order {order.po_number}",
    )
    parties = Table(
        [[_party_block("FROM", order.company, styles), _party_block("TO (SUPPLIER)", order.supplier, styles)]],
        colWidths=[87 * mm, 87 * mm],
    )
    parties.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    terms = f"{order.payment_terms_days} days" if order.payment_terms_days is not None else "As agreed"
    story: list[object] = [
        _header(order, styles),
        Spacer(1, 8 * mm),
        parties,
        Spacer(1, 6 * mm),
        _paragraph(f"Currency: {order.currency_code}    Payment terms: {terms}", styles["body"]),
        Spacer(1, 4 * mm),
        _lines_table(order, brand, styles),
        Spacer(1, 6 * mm),
        _totals_table(order, styles),
    ]
    if order.notes:
        story.extend([Spacer(1, 6 * mm), Paragraph("Notes", styles["label"]), _paragraph(order.notes, styles["body"])])
    doc.build(story)
    return buffer.getvalue()
