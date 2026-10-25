"""Small, valid files built in memory for upload tests."""

import io

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
