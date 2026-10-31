"""Telling what an uploaded file really is from its bytes. The client's declared type and file name are never used."""

import io
import zipfile

PDF = "pdf"
PNG = "png"
JPEG = "jpg"
XLSX = "xlsx"
CSV = "csv"

# kind -> (content type served back, extension used in the storage key)
KINDS: dict[str, tuple[str, str]] = {
    PDF: ("application/pdf", "pdf"),
    PNG: ("image/png", "png"),
    JPEG: ("image/jpeg", "jpg"),
    XLSX: ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"),
    CSV: ("text/csv", "csv"),
}
ATTACHMENT_KINDS = frozenset(KINDS)
# Scans and photos of paperwork: what suppliers upload as invoices and compliance documents.
DOCUMENT_KINDS = frozenset({PDF, PNG, JPEG})

_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"%PDF-", PDF),
    (b"\x89PNG\r\n\x1a\n", PNG),
    (b"\xff\xd8\xff", JPEG),
)
_ZIP_SIGNATURE = b"PK\x03\x04"
_XLSX_REQUIRED_PARTS = frozenset({"[Content_Types].xml", "xl/workbook.xml"})
# A spreadsheet that unpacks to more than this is treated as a zip bomb rather than opened.
_MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
_ALLOWED_CONTROL_CHARACTERS = frozenset("\t\n\r")
_CSV_DELIMITERS = (",", ";", "\t", "|")


def _is_xlsx(data: bytes) -> bool:
    """A zip that holds the parts every Excel workbook has; a bare zip or a docx does not qualify."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if sum(info.file_size for info in infos) > _MAX_UNCOMPRESSED_BYTES:
                return False
            names = {info.filename for info in infos}
    except (zipfile.BadZipFile, OSError):
        return False
    return names >= _XLSX_REQUIRED_PARTS


def _is_csv(data: bytes) -> bool:
    """Plain UTF-8 text without binary control characters. A CSV has no signature, so this is the whole check."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return False
    stripped = text.strip()
    if not stripped or stripped.startswith("<"):  # empty, or markup rather than data
        return False
    if not all(char >= " " or char in _ALLOWED_CONTROL_CHARACTERS for char in text):
        return False
    # Without a delimiter in the header line it is just some text (a truncated PDF header, a note), not a table.
    first_line = stripped.splitlines()[0]
    return any(delimiter in first_line for delimiter in _CSV_DELIMITERS)


def detect_file_type(data: bytes, allowed: frozenset[str]) -> tuple[str, str] | None:
    """(content type, extension) when the bytes are one of the ``allowed`` kinds; otherwise ``None``."""
    kind: str | None = None
    for signature, signed_kind in _SIGNATURES:
        if data.startswith(signature):
            kind = signed_kind
            break
    else:
        if data.startswith(_ZIP_SIGNATURE) and _is_xlsx(data):
            kind = XLSX
        elif not data.startswith(_ZIP_SIGNATURE) and _is_csv(data):
            kind = CSV
    return KINDS[kind] if kind in allowed else None
