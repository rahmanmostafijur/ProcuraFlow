from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.po_version import PurchaseOrderVersion
from app.models.user import User
from app.schemas.person import PersonRead
from app.schemas.po_version import PurchaseOrderVersionRead


async def to_version_read(db: AsyncSession, version: PurchaseOrderVersion) -> PurchaseOrderVersionRead:
    creator = await db.get(User, version.created_by)
    assert creator is not None  # noqa: S101 - the column is a non-null foreign key
    return _build(version, creator)


async def to_version_reads(db: AsyncSession, versions: list[PurchaseOrderVersion]) -> list[PurchaseOrderVersionRead]:
    user_ids = {version.created_by for version in versions}
    people = {user.id: user for user in (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars()}
    return [_build(version, people[version.created_by]) for version in versions]


def _build(version: PurchaseOrderVersion, creator: User) -> PurchaseOrderVersionRead:
    return PurchaseOrderVersionRead(
        id=version.id,
        po_id=version.po_id,
        version=version.version,
        status=version.status,
        reason=version.reason,
        created_by_person=PersonRead(id=creator.id, full_name=creator.full_name),
        created_at=version.created_at,
        decided_at=version.decided_at,
        changes=version.changes,
        snapshot=version.snapshot,
    )
