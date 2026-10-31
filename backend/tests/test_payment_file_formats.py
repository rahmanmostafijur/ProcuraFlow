"""The SEPA and ACH file builders on their own: structure, control totals, padding and escaping."""

import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.services.nacha_file import RECORD_LENGTH, AchFormatError, alpha, build_nacha_file, numeric
from app.services.payment_file_types import Payer, PaymentLine, next_business_day, to_cents
from app.services.sepa_file import NAMESPACE, build_sepa_file, sepa_text
from tests.payment_file_helpers import BOA_ROUTING, CHASE_ROUTING, FRENCH_IBAN, GERMAN_IBAN, OUR_IBAN, OUR_ROUTING

NOW = datetime(2026, 11, 2, 9, 5, 7, tzinfo=UTC)
PAYER = Payer(
    name="Acme Corp",
    iban=OUR_IBAN,
    bic="ABNANL2A",
    routing_number=OUR_ROUTING,
    account_number="99",
    ach_company_id="1234567890",
)


def _ach_line(
    reference: str, amount: str, routing: str = CHASE_ROUTING, name: str = "Test Supplier Inc"
) -> PaymentLine:
    return PaymentLine(reference, name, Decimal(amount), None, None, "000123456789", routing)


def _sepa_line(reference: str, amount: str, iban: str = GERMAN_IBAN, name: str = "Test Supplier GmbH") -> PaymentLine:
    return PaymentLine(reference, name, Decimal(amount), iban, "COBADEFFXXX", None, None)


def _records(data: bytes) -> list[str]:
    return data.decode("ascii").split("\r\n")[:-1]


@pytest.mark.parametrize("entry_count", [1, 2, 5, 6, 7, 8, 18])
def test_ach_records_are_94_characters_and_padded_to_blocks_of_ten(entry_count: int) -> None:
    lines = [_ach_line(f"INV-{n}", "10.00") for n in range(entry_count)]

    records = _records(
        build_nacha_file(created_at=NOW, effective_date=date(2026, 11, 3), payer=PAYER, lines=lines, run_id=7)
    )

    assert all(len(record) == RECORD_LENGTH for record in records)
    assert len(records) % 10 == 0
    assert len(records) - (entry_count + 4) < 10  # no more padding than needed
    assert all(set(record) == {"9"} for record in records[entry_count + 4 :])
    file_control = records[entry_count + 3]
    assert file_control.startswith("9")
    assert int(file_control[7:13]) == len(records) // 10


def test_ach_headers_controls_and_entry_hash() -> None:
    lines = [
        _ach_line("INV-1", "100.50"),
        _ach_line("INV-2", "0.05", BOA_ROUTING, "Östlich & Söhne"),
        _ach_line("INV-3", "2500"),
    ]

    records = _records(
        build_nacha_file(created_at=NOW, effective_date=date(2026, 11, 3), payer=PAYER, lines=lines, run_id=7)
    )

    file_header, batch_header, *entries, batch_control, file_control = records[:7]
    assert file_header[:3] == "101"
    assert file_header[3:13] == " " + OUR_ROUTING
    assert file_header[13:23] == "1234567890"
    assert (file_header[23:29], file_header[29:33]) == ("261102", "0905")
    assert file_header[33:37] == "A094"  # id modifier and record size
    assert file_header[37:40] == "101"  # blocking factor 10, format code 1
    assert file_header[63:86].strip() == "ACME CORP"
    assert file_header[86:94] == "00000007"

    assert batch_header[:4] == "5220"
    assert batch_header[4:20].strip() == "ACME CORP"
    assert batch_header[40:50] == "1234567890"
    assert batch_header[50:53] == "CCD"
    assert batch_header[69:75] == "261103"
    assert batch_header[78] == "1"
    assert batch_header[79:87] == OUR_ROUTING[:8]
    assert batch_header[87:94] == "0000001"

    assert len(entries) == 3
    assert [entry[:3] for entry in entries] == ["622", "622", "622"]
    assert [entry[3:12] for entry in entries] == [CHASE_ROUTING, BOA_ROUTING, CHASE_ROUTING]
    assert [int(entry[29:39]) for entry in entries] == [10050, 5, 250000]
    assert entries[1][54:76].strip() == "OSTLICH & SOHNE"
    assert [entry[78] for entry in entries] == ["0", "0", "0"]
    assert [entry[79:94] for entry in entries] == [f"{OUR_ROUTING[:8]}{n:07d}" for n in (1, 2, 3)]

    expected_hash = (int(CHASE_ROUTING[:8]) * 2 + int(BOA_ROUTING[:8])) % 10**10
    total_credit = 10050 + 5 + 250000
    assert batch_control[:10] == "8220000003"
    assert int(batch_control[10:20]) == expected_hash
    assert (int(batch_control[20:32]), int(batch_control[32:44])) == (0, total_credit)
    assert batch_control[44:54] == "1234567890"
    assert batch_control[79:87] == OUR_ROUTING[:8]
    assert file_control[:13] == "9000001000001"
    assert int(file_control[13:21]) == 3
    assert int(file_control[21:31]) == expected_hash
    assert (int(file_control[31:43]), int(file_control[43:55])) == (0, total_credit)


def test_ach_field_helpers() -> None:
    assert alpha("Café Müller & Co", 10) == "CAFE MULLE"
    assert alpha("ab", 5) == "AB   "
    assert numeric(42, 6) == "000042"
    with pytest.raises(AchFormatError):
        numeric(1_000_000, 6)


def test_an_amount_too_large_for_an_entry_is_refused() -> None:
    with pytest.raises(AchFormatError):
        build_nacha_file(
            created_at=NOW,
            effective_date=date(2026, 11, 3),
            payer=PAYER,
            lines=[_ach_line("INV-1", "100000000.00")],
            run_id=1,
        )


def test_the_sepa_file_has_matching_counts_control_sums_and_transactions() -> None:
    lines = [_sepa_line("INV-1", "100.10"), _sepa_line("INV-2", "250.25", FRENCH_IBAN, "Dupont SARL")]

    root = ET.fromstring(  # noqa: S314 - parsing the builder's own output
        build_sepa_file(
            message_id="PAY-2026-00001",
            created_at=NOW,
            execution_date=date(2026, 11, 3),
            payer=PAYER,
            lines=lines,
            currency="EUR",
        )
    )

    ns = {"p": NAMESPACE}
    assert root.tag == f"{{{NAMESPACE}}}Document"
    header = root.find("p:CstmrCdtTrfInitn/p:GrpHdr", ns)
    batch = root.find("p:CstmrCdtTrfInitn/p:PmtInf", ns)
    assert header is not None
    assert batch is not None
    assert header.findtext("p:MsgId", namespaces=ns) == "PAY-2026-00001"
    assert header.findtext("p:CreDtTm", namespaces=ns) == "2026-11-02T09:05:07"
    assert (header.findtext("p:NbOfTxs", namespaces=ns), header.findtext("p:CtrlSum", namespaces=ns)) == ("2", "350.35")
    assert (batch.findtext("p:NbOfTxs", namespaces=ns), batch.findtext("p:CtrlSum", namespaces=ns)) == ("2", "350.35")
    assert batch.findtext("p:PmtMtd", namespaces=ns) == "TRF"
    assert batch.findtext("p:PmtTpInf/p:SvcLvl/p:Cd", namespaces=ns) == "SEPA"
    assert batch.findtext("p:ReqdExctnDt", namespaces=ns) == "2026-11-03"
    assert batch.findtext("p:DbtrAcct/p:Id/p:IBAN", namespaces=ns) == OUR_IBAN
    assert batch.findtext("p:DbtrAgt/p:FinInstnId/p:BIC", namespaces=ns) == "ABNANL2A"
    transactions = batch.findall("p:CdtTrfTxInf", ns)
    assert [t.findtext("p:PmtId/p:EndToEndId", namespaces=ns) for t in transactions] == ["INV-1", "INV-2"]
    assert [t.findtext("p:CdtrAcct/p:Id/p:IBAN", namespaces=ns) for t in transactions] == [GERMAN_IBAN, FRENCH_IBAN]
    assert [t.findtext("p:Cdtr/p:Nm", namespaces=ns) for t in transactions] == ["Test Supplier GmbH", "Dupont SARL"]
    amounts = [t.find("p:Amt/p:InstdAmt", ns) for t in transactions]
    assert [(a.text, a.get("Ccy")) for a in amounts if a is not None] == [("100.10", "EUR"), ("250.25", "EUR")]
    total = sum(Decimal(a.text or "0") for a in amounts if a is not None)
    assert str(total) == header.findtext("p:CtrlSum", namespaces=ns)


def test_sepa_text_is_escaped_and_reduced_to_the_allowed_characters() -> None:
    line = _sepa_line("INV <1> & co", "10.00", name='Müller & Söhne <"GmbH">')

    document = build_sepa_file(
        message_id="PAY-1", created_at=NOW, execution_date=date(2026, 11, 3), payer=PAYER, lines=[line], currency="EUR"
    )

    root = ET.fromstring(document)  # noqa: S314 - parsing the builder's own output
    names = [element.text for element in root.iter(f"{{{NAMESPACE}}}Nm")]
    assert b"<GmbH>" not in document
    assert "Muller Sohne GmbH" in names
    assert root.findtext(f".//{{{NAMESPACE}}}EndToEndId") == "INV 1 co"
    assert sepa_text("a" * 100, 70) == "a" * 70
    assert sepa_text("  spaced   out ", 35) == "spaced out"


def test_a_missing_payer_bic_is_stated_not_invented() -> None:
    payer = Payer("Acme Corp", OUR_IBAN, None, None, None, None)

    root = ET.fromstring(  # noqa: S314 - parsing the builder's own output
        build_sepa_file(
            message_id="PAY-1",
            created_at=NOW,
            execution_date=date(2026, 11, 3),
            payer=payer,
            lines=[PaymentLine("INV-1", "Acme", Decimal("1"), GERMAN_IBAN, None, None, None)],
            currency="EUR",
        )
    )

    assert (
        root.findtext(f".//{{{NAMESPACE}}}DbtrAgt/{{{NAMESPACE}}}FinInstnId/{{{NAMESPACE}}}Othr/{{{NAMESPACE}}}Id")
        == "NOTPROVIDED"
    )
    assert root.find(f".//{{{NAMESPACE}}}CdtrAgt") is None


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 11, 2), date(2026, 11, 3)),
        (date(2026, 11, 6), date(2026, 11, 9)),
        (date(2026, 11, 7), date(2026, 11, 9)),
    ],
)
def test_the_value_date_is_the_next_weekday(day: date, expected: date) -> None:
    assert next_business_day(day) == expected


def test_amounts_become_whole_cents_half_up() -> None:
    assert to_cents(Decimal("10.005")) == 1001
    assert to_cents(Decimal("0.01")) == 1
