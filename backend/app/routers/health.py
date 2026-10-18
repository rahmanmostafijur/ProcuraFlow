import asyncio
import logging

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.deps import DbSession

logger = logging.getLogger(__name__)

# A cold serverless database can take a few seconds to resume; beyond this the API is not usefully ready.
READINESS_TIMEOUT_SECONDS = 10

router = APIRouter(tags=["health"])


@router.get("/health")
async def liveness() -> dict[str, str]:
    """The process is up. Does not touch the database, so it never wakes it."""
    return {"status": "ok"}


@router.get("/ready")
async def readiness(db: DbSession) -> JSONResponse:
    """The API can serve traffic: the database answers a trivial query."""
    try:
        await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=READINESS_TIMEOUT_SECONDS)
    except (SQLAlchemyError, OSError, TimeoutError):
        logger.warning("readiness check failed", exc_info=True)
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"status": "unavailable"})
    return JSONResponse(content={"status": "ready"})
