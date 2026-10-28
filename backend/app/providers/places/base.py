from __future__ import annotations

from typing import Protocol

from app.schemas.travel import Place, PlaceSearchResult


class PlacesProvider(Protocol):
    name: str
    is_live: bool

    async def search(self, query: str, *, near: str | None = None, lat: float | None = None,
                     lng: float | None = None, category: str | None = None, limit: int = 10) -> PlaceSearchResult: ...

    async def details(self, place_id: str) -> Place | None: ...

    async def photo_uri(self, photo_name: str, max_width: int = 800) -> str | None: ...
