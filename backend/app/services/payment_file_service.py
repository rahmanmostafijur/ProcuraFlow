"""The bank file of a released payment run: SEPA credit transfer (EUR) or NACHA/ACH (USD).

The file is generated once. The first export builds it from the run and the suppliers' current bank details, stores
the bytes and their SHA-256, and audits it; every later request returns the stored bytes, so what the bank received
is exactly what can be downloaded again, even if bank details change afterwards. An export is refused, with every
problem listed, when the run is not released or a supplier (or the company) lacks the details the format needs.
"""

import hashlib
from datetime import UTC, date, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company_settings import CompanySettings
from app.models.enums import PaymentFileFormat, PaymentRunStatus
from app.models.payment import PaymentRun
from app.models.payment_file import PaymentRunFile
from app.models.supplier_bank import SupplierBankDetails
from app.models.user import User
from app.schemas.payment_file import PaymentFileRead
from app.schemas.person import PersonRead
from app.services.audit_service import record_audit_event
from app.services.company_settings_service import get_company_settings
from app.services.nacha_file import build_nacha_file
from app.services.payment_file_types import Payer, PaymentLine, next_business_day
from app.services.payment_run_service import get_run
from app.services.sepa_file import build_sepa_file
from app.services.supplier_bank_service import get_current
from app.storage import StorageBackend, StoredObjectNotFoundError, new_storage_key

# The EU member states, the other EEA states and the remaining SEPA scheme members.
SEPA_COUNTRIES = frozenset(
    {
        *("AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE"),
        *("IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"),
        *("IS", "LI", "NO", "CH", "GB", "MC", "SM", "AD", "VA"),
    }
)
FORMAT_BY_CURRENCY = {"EUR": PaymentFileFormat.SEPA_PAIN001, "USD": PaymentFileFormat.NACHA_ACH}
FILE_TYPES = {
    PaymentFileFormat.SEPA_PAIN001: ("application/xml", "xml", "sepa.xml"),
    PaymentFileFormat.NACHA_ACH: ("text/plain", "ach", "ach.txt"),
}


def _error(code: int, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail=message)


def _payer(company: CompanySettings) -> Payer:
    return Payer(
        name=company.legal_name or company.company_name,
        iban=company.payer_iban,
        bic=company.payer_bic,
        routing_number=company.payer_routing_number,
        account_number=company.payer_account_number,
        ach_company_id=company.ach_company_id,
    )


def _company_problems(file_format: PaymentFileFormat, payer: Payer) -> list[str]:
    if file_format == PaymentFileFormat.SEPA_PAIN001:
        return [] if payer.iban else ["Company settings: the payer IBAN is not set"]
    missing = []
    if not payer.routing_number:
        missing.append("the payer routing number")
    if not payer.ach_company_id:
        missing.append("the ACH company ID")
    return [f"Company settings: {', '.join(missing)} not set"] if missing else []


def _supplier_problems(file_format: PaymentFileFormat, details: SupplierBankDetails | None) -> list[str]:
    if details is None:
        return ["no approved bank details"]
    problems = []
    if file_format == PaymentFileFormat.SEPA_PAIN001:
        if not details.iban:
            problems.append("missing IBAN")
        if details.bank_country not in SEPA_COUNTRIES:
            problems.append(f"bank country {details.bank_country} is outside the SEPA area")
    else:
        if not details.routing_number:
            problems.append("missing routing number")
        if not details.bank_account_number:
            problems.append("missing bank account number")
        elif len(details.bank_account_number) > 17:  # noqa: PLR2004 - the width of the ACH account field
            problems.append("the account number is longer than ACH allows (17)")
        if details.bank_country != "US":
            problems.append(f"bank country {details.bank_country} is not US")
    return problems


async def _lines(
    db: AsyncSession, run: PaymentRun, file_format: PaymentFileFormat
) -> tuple[list[PaymentLine], list[str]]:
    lines: list[PaymentLine] = []
    problems: list[str] = []
    for item in run.items:
        supplier = item.invoice.supplier
        details = await get_current(db, supplier.id)
        found = _supplier_problems(file_format, details)
        if found or details is None:
            problems.append(f"{supplier.name} (invoice {item.invoice.invoice_number}): {'; '.join(found)}")
            continue
        lines.append(
            PaymentLine(
                reference=item.invoice.invoice_number,
                payee_name=details.bank_account_name or supplier.name,
                amount=item.amount,
                iban=details.iban,
                bic=details.bic,
                account_number=details.bank_account_number,
                routing_number=details.routing_number,
            )
        )
    return lines, problems


def _build(
    run: PaymentRun, file_format: PaymentFileFormat, payer: Payer, lines: list[PaymentLine], today: date, now: datetime
) -> bytes:
    effective = next_business_day(today)
    if file_format == PaymentFileFormat.SEPA_PAIN001:
        return build_sepa_file(
            message_id=run.number,
            created_at=now,
            execution_date=effective,
            payer=payer,
            lines=lines,
            currency=run.currency_code,
        )
    return build_nacha_file(created_at=now, effective_date=effective, payer=payer, lines=lines, run_id=run.id)


async def _find_file(db: AsyncSession, run_id: int) -> PaymentRunFile | None:
    found: PaymentRunFile | None = await db.scalar(select(PaymentRunFile).where(PaymentRunFile.run_id == run_id))
    return found


async def _to_read(db: AsyncSession, file: PaymentRunFile, run: PaymentRun) -> PaymentFileRead:
    creator = await db.get(User, file.created_by)
    assert creator is not None  # noqa: S101 - the column is a non-null foreign key
    return PaymentFileRead(
        id=file.id,
        run_id=run.id,
        run_number=run.number,
        file_format=PaymentFileFormat(file.file_format),
        filename=file.filename,
        content_type=file.content_type,
        size_bytes=file.size_bytes,
        sha256=file.sha256,
        currency_code=run.currency_code,
        transaction_count=len(run.items),
        total=run.total,
        created_by=PersonRead(id=creator.id, full_name=creator.full_name),
        created_at=file.created_at,
    )


async def generate_file(
    db: AsyncSession, storage: StorageBackend, actor: User, run_id: int, today: date
) -> tuple[PaymentFileRead, bool]:
    """The run's bank file and whether this call created it. Calling again returns the stored one unchanged."""
    run = await get_run(db, run_id, for_update=True)
    if run.status != PaymentRunStatus.RELEASED:
        raise _error(
            status.HTTP_409_CONFLICT,
            f"Only a released payment run can be exported; {run.number} is '{run.status.value}'",
        )
    existing = await _find_file(db, run.id)
    if existing is not None:
        return await _to_read(db, existing, run), False

    file_format = FORMAT_BY_CURRENCY.get(run.currency_code)
    if file_format is None:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"No bank file format exists for {run.currency_code}: SEPA is for EUR and ACH is for USD",
        )
    payer = _payer(await get_company_settings(db))
    lines, problems = await _lines(db, run, file_format)
    problems = [*_company_problems(file_format, payer), *problems]
    if problems:
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Cannot export {run.number}: " + " | ".join(problems))

    now = datetime.now(UTC)
    data = _build(run, file_format, payer, lines, today, now)
    content_type, extension, suffix = FILE_TYPES[file_format]
    key = new_storage_key("payment-files", extension)
    await storage.save(key, data, content_type)
    file = PaymentRunFile(
        run_id=run.id,
        file_format=file_format.value,
        filename=f"{run.number}-{suffix}",
        content_type=content_type,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        storage_key=key,
        created_by=actor.id,
    )
    db.add(file)
    try:
        await db.flush()
    except IntegrityError:
        # Another request exported the run between the check and the insert; theirs is the file.
        await db.rollback()
        await storage.delete(key)
        winner = await _find_file(db, run_id)
        if winner is None:
            raise
        return await _to_read(db, winner, await get_run(db, run_id)), False
    await record_audit_event(
        db,
        user_id=actor.id,
        action="payment_file_generated",
        entity_type="payment_run",
        entity_id=run.id,
        extra_data={
            "number": run.number,
            "format": file_format.value,
            "transactions": len(lines),
            "total": str(run.total),
            "sha256": file.sha256,
        },
    )
    try:
        await db.commit()
    except Exception:
        await storage.delete(key)
        raise
    await db.refresh(file)
    return await _to_read(db, file, await get_run(db, run_id)), True


async def get_file_info(db: AsyncSession, run_id: int) -> PaymentFileRead:
    run = await get_run(db, run_id)
    file = await _find_file(db, run.id)
    if file is None:
        raise _error(status.HTTP_404_NOT_FOUND, "This payment run has not been exported yet")
    return await _to_read(db, file, run)


async def read_file(
    db: AsyncSession, storage: StorageBackend, actor: User, run_id: int
) -> tuple[PaymentRunFile, bytes]:
    run = await get_run(db, run_id)
    file = await _find_file(db, run.id)
    if file is None:
        raise _error(status.HTTP_404_NOT_FOUND, "This payment run has not been exported yet")
    try:
        data = await storage.read(file.storage_key)
    except StoredObjectNotFoundError as exc:
        raise _error(status.HTTP_404_NOT_FOUND, "The stored payment file is missing") from exc
    if hashlib.sha256(data).hexdigest() != file.sha256:
        raise _error(status.HTTP_500_INTERNAL_SERVER_ERROR, "The stored payment file failed its integrity check")
    await record_audit_event(
        db,
        user_id=actor.id,
        action="payment_file_downloaded",
        entity_type="payment_run",
        entity_id=run.id,
        extra_data={"number": run.number, "sha256": file.sha256},
    )
    await db.commit()
    return file, data
