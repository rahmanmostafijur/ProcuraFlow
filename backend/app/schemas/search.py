"""Response shapes of GET /search. Imported by app/routers/search.py and app/services/search_service.py."""

from pydantic import BaseModel


class SearchItem(BaseModel):
    id: int
    title: str
    subtitle: str | None
    status: str | None
    # A frontend route, so the command palette can navigate without knowing the entity.
    url: str


class SearchGroup(BaseModel):
    type: str
    label: str
    items: list[SearchItem]


class SearchResponse(BaseModel):
    query: str
    groups: list[SearchGroup]
