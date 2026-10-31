"""A SEPA credit transfer file: ISO 20022 ``pain.001.001.03``, built with the standard library's ElementTree.

ElementTree escapes every text value, so a supplier name containing ``&`` or ``<`` cannot break the document or
inject markup. Names and references are also folded to the restricted character set SEPA banks accept.
"""

import re
import xml.etree.ElementTree as ET
from datetime import date, datetime
from decimal import Decimal

from app.services.payment_file_types import Payer, PaymentLine, ascii_text

NAMESPACE = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"
NAME_LENGTH = 70
REFERENCE_LENGTH = 35
REMITTANCE_LENGTH = 140
NOT_PROVIDED = "NOTPROVIDED"
_DISALLOWED = re.compile(r"[^A-Za-z0-9/\-?:().,'+ ]")

ET.register_namespace("", NAMESPACE)


def sepa_text(value: str, limit: int) -> str:
    """The value reduced to the SEPA character set, single-spaced and cut to ``limit`` characters."""
    cleaned = re.sub(r"\s+", " ", _DISALLOWED.sub(" ", ascii_text(value))).strip()
    return cleaned[:limit]


def _element(parent: ET.Element, name: str, text: str | None = None, **attributes: str) -> ET.Element:
    child = ET.SubElement(parent, f"{{{NAMESPACE}}}{name}", attributes)
    if text is not None:
        child.text = text
    return child


def _amount(value: Decimal) -> str:
    return f"{value:.2f}"


def _agent(parent: ET.Element, tag: str, bic: str | None, *, required: bool) -> None:
    if not bic and not required:
        return
    institution = _element(_element(parent, tag), "FinInstnId")
    if bic:
        _element(institution, "BIC", bic)
    else:
        # An IBAN identifies the bank, so a missing BIC is stated rather than invented.
        _element(_element(institution, "Othr"), "Id", NOT_PROVIDED)


def _transaction(payment: ET.Element, line: PaymentLine, currency: str) -> None:
    transfer = _element(payment, "CdtTrfTxInf")
    reference = sepa_text(line.reference, REFERENCE_LENGTH) or NOT_PROVIDED
    _element(_element(transfer, "PmtId"), "EndToEndId", reference)
    _element(_element(transfer, "Amt"), "InstdAmt", _amount(line.amount), Ccy=currency)
    _agent(transfer, "CdtrAgt", line.bic, required=False)
    _element(_element(transfer, "Cdtr"), "Nm", sepa_text(line.payee_name, NAME_LENGTH))
    _element(_element(_element(transfer, "CdtrAcct"), "Id"), "IBAN", line.iban)
    _element(_element(transfer, "RmtInf"), "Ustrd", sepa_text(f"Invoice {line.reference}", REMITTANCE_LENGTH))


def build_sepa_file(
    *,
    message_id: str,
    created_at: datetime,
    execution_date: date,
    payer: Payer,
    lines: list[PaymentLine],
    currency: str,
) -> bytes:
    total = sum((line.amount for line in lines), Decimal(0))
    root = ET.Element(f"{{{NAMESPACE}}}Document")
    initiation = _element(root, "CstmrCdtTrfInitn")

    header = _element(initiation, "GrpHdr")
    _element(header, "MsgId", sepa_text(message_id, REFERENCE_LENGTH))
    _element(header, "CreDtTm", created_at.strftime("%Y-%m-%dT%H:%M:%S"))
    _element(header, "NbOfTxs", str(len(lines)))
    _element(header, "CtrlSum", _amount(total))
    _element(_element(header, "InitgPty"), "Nm", sepa_text(payer.name, NAME_LENGTH))

    batch = _element(initiation, "PmtInf")
    _element(batch, "PmtInfId", sepa_text(message_id, REFERENCE_LENGTH))
    _element(batch, "PmtMtd", "TRF")
    _element(batch, "BtchBookg", "true")
    _element(batch, "NbOfTxs", str(len(lines)))
    _element(batch, "CtrlSum", _amount(total))
    _element(_element(_element(batch, "PmtTpInf"), "SvcLvl"), "Cd", "SEPA")
    _element(batch, "ReqdExctnDt", execution_date.isoformat())
    _element(_element(batch, "Dbtr"), "Nm", sepa_text(payer.name, NAME_LENGTH))
    _element(_element(_element(batch, "DbtrAcct"), "Id"), "IBAN", payer.iban)
    _agent(batch, "DbtrAgt", payer.bic, required=True)
    _element(batch, "ChrgBr", "SLEV")
    for line in lines:
        _transaction(batch, line, currency)
    document: bytes = ET.tostring(root, encoding="UTF-8", xml_declaration=True)
    return document
