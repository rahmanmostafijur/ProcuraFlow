"""A NACHA / ACH credit file: fixed-width 94-character records padded to blocks of ten.

One batch of corporate credits (service class 220, SEC code CCD) that pays suppliers from the company's account.
Record layouts follow the NACHA Operating Rules: 1 file header, 5 batch header, 6 entry details, 8 batch control and
9 file control, then lines of nines until the record count is a multiple of ten. Field widths are asserted, so a
mistake in a layout fails loudly instead of producing a file the bank rejects.
"""

from datetime import date, datetime

from app.services.payment_file_types import Payer, PaymentLine, ascii_text, to_cents

RECORD_LENGTH = 94
BLOCK_SIZE = 10
LINE_END = "\r\n"
SERVICE_CLASS_CREDITS_ONLY = "220"
TRANSACTION_CODE_CHECKING_CREDIT = "22"
MAX_ENTRY_CENTS = 10**10 - 1
HASH_MODULUS = 10**10


class AchFormatError(ValueError):
    """A value does not fit its ACH field."""


def alpha(value: str, width: int) -> str:
    """Upper-case ASCII, left-justified and space-padded to ``width`` (cut if longer)."""
    cleaned = " ".join(ascii_text(value).upper().split())
    return cleaned[:width].ljust(width)


def numeric(value: int, width: int) -> str:
    text = str(value)
    if value < 0 or len(text) > width:
        raise AchFormatError(f"The number {value} does not fit a {width}-digit field")
    return text.zfill(width)


def _record(*fields: str) -> str:
    record = "".join(fields)
    if len(record) != RECORD_LENGTH:
        raise AchFormatError(f"An ACH record must be {RECORD_LENGTH} characters, this one is {len(record)}")
    return record


def _routing_parts(routing: str) -> tuple[str, str]:
    """The 8-digit bank identifier and the check digit, which travel in separate fields of an entry."""
    return routing[:8], routing[8]


def _file_header(payer: Payer, created_at: datetime, run_id: int) -> str:
    routing = payer.routing_number or ""
    return _record(
        "1",
        "01",
        " " + routing,
        alpha(payer.ach_company_id or "", 10),
        created_at.strftime("%y%m%d"),
        created_at.strftime("%H%M"),
        "A",
        "094",
        "10",
        "1",
        alpha("ORIGINATING BANK", 23),
        alpha(payer.name, 23),
        numeric(run_id, 8),
    )


def _batch_header(payer: Payer, effective_date: date) -> str:
    odfi, _ = _routing_parts(payer.routing_number or "")
    return _record(
        "5",
        SERVICE_CLASS_CREDITS_ONLY,
        alpha(payer.name, 16),
        alpha("", 20),
        alpha(payer.ach_company_id or "", 10),
        "CCD",
        alpha("SUPPLIERS", 10),
        alpha("", 6),
        effective_date.strftime("%y%m%d"),
        alpha("", 3),
        "1",
        odfi,
        numeric(1, 7),
    )


def _entry(line: PaymentLine, odfi: str, sequence: int) -> tuple[str, int]:
    """The entry detail record and the 8-digit bank identifier it contributes to the entry hash."""
    rdfi, check_digit = _routing_parts(line.routing_number or "")
    cents = to_cents(line.amount)
    if cents > MAX_ENTRY_CENTS:
        raise AchFormatError(f"The amount {line.amount} is too large for an ACH entry")
    record = _record(
        "6",
        TRANSACTION_CODE_CHECKING_CREDIT,
        rdfi,
        check_digit,
        alpha(line.account_number or "", 17),
        numeric(cents, 10),
        alpha(line.reference, 15),
        alpha(line.payee_name, 22),
        alpha("", 2),
        "0",
        odfi + numeric(sequence, 7),
    )
    return record, int(rdfi)


def build_nacha_file(
    *, created_at: datetime, effective_date: date, payer: Payer, lines: list[PaymentLine], run_id: int
) -> bytes:
    odfi, _ = _routing_parts(payer.routing_number or "")
    entries = [_entry(line, odfi, sequence) for sequence, line in enumerate(lines, start=1)]
    entry_hash = sum(rdfi for _, rdfi in entries) % HASH_MODULUS
    total_credit = sum(to_cents(line.amount) for line in lines)
    company_id = alpha(payer.ach_company_id or "", 10)

    records = [
        _file_header(payer, created_at, run_id),
        _batch_header(payer, effective_date),
        *(record for record, _ in entries),
        _record(
            "8",
            SERVICE_CLASS_CREDITS_ONLY,
            numeric(len(entries), 6),
            numeric(entry_hash, 10),
            numeric(0, 12),
            numeric(total_credit, 12),
            company_id,
            alpha("", 19),
            alpha("", 6),
            odfi,
            numeric(1, 7),
        ),
    ]
    records_with_file_control = len(records) + 1
    blocks = -(-records_with_file_control // BLOCK_SIZE)
    records.append(
        _record(
            "9",
            numeric(1, 6),
            numeric(blocks, 6),
            numeric(len(entries), 8),
            numeric(entry_hash, 10),
            numeric(0, 12),
            numeric(total_credit, 12),
            alpha("", 39),
        )
    )
    records.extend("9" * RECORD_LENGTH for _ in range(blocks * BLOCK_SIZE - len(records)))
    return (LINE_END.join(records) + LINE_END).encode("ascii")
