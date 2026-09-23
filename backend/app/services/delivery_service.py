from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.delivery import Delivery
from app.models.enums import DeliveryStatus


async def get_on_time_delivery_rate(db: AsyncSession) -> float:
    result = await db.execute(
        select(Delivery.status, func.count())
        .where(Delivery.actual_date.is_not(None))
        .group_by(Delivery.status)
    )
    counts = dict(result.all())
    total = sum(counts.values())
    if total == 0:
        return 0.0
    on_time = counts.get(DeliveryStatus.ON_TIME, 0)
    return round((on_time / total) * 100, 1)
