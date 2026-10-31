from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.schemas.search import SearchResponse
from app.services import search_service as service

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
async def search(
    db: DbSession,
    user: CurrentUser,
    q: Annotated[str, Query(max_length=service.MAX_QUERY_LENGTH)] = "",
    limit: Annotated[int, Query(ge=1)] = service.DEFAULT_LIMIT,
) -> SearchResponse:
    """Command-palette search across what the signed-in user may already list; see the service for the scope.
    A limit above the maximum is capped rather than refused, so a client with a stale constant still works."""
    return await service.search(db, user, q, limit)
