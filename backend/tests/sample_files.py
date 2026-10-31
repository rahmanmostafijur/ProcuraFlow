"""Small, valid files built in memory for upload tests."""

import io
import zipfile

from PIL import Image


def image_bytes(image_format: str = "PNG", size: tuple[int, int] = (8, 8)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color=(15, 118, 110)).save(buffer, format=image_format)
    return buffer.getvalue()


def pdf_bytes() -> bytes:
    # The smallest structure PDF readers and signature checks accept: header, one empty page, trailer.
    return (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 10 10]>>endobj\n"
        b"trailer<</Root 1 0 R>>\n%%EOF\n"
    )


def xlsx_bytes() -> bytes:
    # Not a spreadsheet anyone could open, but it has the parts that make a zip an Excel workbook.
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")
    return buffer.getvalue()


def csv_bytes() -> bytes:
    return b"sku,name,quantity\nA-1,Widget,3\n"
