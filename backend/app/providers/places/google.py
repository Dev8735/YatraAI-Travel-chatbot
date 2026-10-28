"""Google Places API (New) adapter.

Docs: https://developers.google.com/maps/documentation/places/web-service/op-overview
Photos are served through our /api/places/photo proxy, which asks Google for a short-lived
photoUri (skipHttpRedirect) so the API key never reaches the browser. Required author
attributions are passed through and must be displayed with each photo.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

import httpx

from app.core.errors import ProviderError
from app.core.logging import get_logger
from app.schemas.travel import Attribution, PhotoRef, Place, PlaceSearchResult

log = get_logger(__name__)

BASE = "https://places.googleapis.com/v1"
_FIELDS = [
    "id", "displayName", "formattedAddress", "location", "rating", "userRatingCount", "types", "primaryType",
    "googleMapsUri", "websiteUri", "regularOpeningHours.weekdayDescriptions", "currentOpeningHours.openNow",
    "photos", "priceLevel",
]
SEARCH_MASK = ",".join(f"places.{f}" for f in _FIELDS)
DETAILS_MASK = ",".join(_FIELDS)
PHOTO_NAME_RE = re.compile(r"^places/[A-Za-z0-9_\-]+/photos/[A-Za-z0-9_\-]+$")
PLACE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{10,300}$")

CATEGORY_QUERY = {
    "lodging": "hotels",
    "restaurant": "restaurants",
    "cafe": "cafes",
    "museum": "museums",
    "temple": "temples",
    "beach": "beaches",
    "park": "parks and gardens",
    "shopping": "markets and shopping",
    "tourist_attraction": "tourist attractions",
}
PRICE_LEVELS = {
    "PRICE_LEVEL_FREE": "free", "PRICE_LEVEL_INEXPENSIVE": "inexpensive", "PRICE_LEVEL_MODERATE": "moderate",
    "PRICE_LEVEL_EXPENSIVE": "expensive", "PRICE_LEVEL_VERY_EXPENSIVE": "very expensive",
}


def _num(value: Any, cast: type) -> Any:
    try:
        return cast(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def map_place(raw: dict[str, Any], destination: str | None = None) -> Place | None:
    """Defensive mapping: any field may be missing."""
    place_id = raw.get("id")
    name = (raw.get("displayName") or {}).get("text")
    if not isinstance(place_id, str) or not PLACE_ID_RE.match(place_id) or not name:
        return None
    loc = raw.get("location") or {}
    photos = []
    for p in (raw.get("photos") or [])[:3]:
        pname = p.get("name")
        if not isinstance(pname, str) or not PHOTO_NAME_RE.match(pname):
            continue
        photos.append(PhotoRef(
            url=f"/api/places/photo?name={quote(pname, safe='/')}",
            width=_num(p.get("widthPx"), int), height=_num(p.get("heightPx"), int),
            attributions=[Attribution(name=a.get("displayName") or "Google user", uri=a.get("uri"))
                          for a in (p.get("authorAttributions") or []) if isinstance(a, dict)],
        ))
    rating = _num(raw.get("rating"), float)
    return Place(
        id=place_id,
        name=str(name)[:200],
        address=raw.get("formattedAddress"),
        lat=_num(loc.get("latitude"), float),
        lng=_num(loc.get("longitude"), float),
        category=raw.get("primaryType"),
        types=[t for t in (raw.get("types") or []) if isinstance(t, str)][:8],
        rating=rating if rating is not None and 0 <= rating <= 5 else None,
        user_rating_count=_num(raw.get("userRatingCount"), int),
        price_level=PRICE_LEVELS.get(raw.get("priceLevel") or ""),
        opening_hours=[h for h in ((raw.get("regularOpeningHours") or {}).get("weekdayDescriptions") or [])
                       if isinstance(h, str)],
        open_now=(raw.get("currentOpeningHours") or {}).get("openNow"),
        photos=photos,
        maps_url=raw.get("googleMapsUri"),
        website=raw.get("websiteUri"),
        destination=destination,
        data_origin="live",
        provider="google_places",
        provider_attribution="Google Maps",
    )


class GooglePlacesProvider:
    name = "google_places"
    is_live = True

    def __init__(self, api_key: str, language: str = "en", timeout: float = 10.0,
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._key = api_key
        self._language = language
        self._client = httpx.AsyncClient(timeout=timeout, transport=transport, trust_env=False)

    async def aclose(self) -> None:
        await self._client.aclose()

    def _headers(self, mask: str) -> dict[str, str]:
        return {"X-Goog-Api-Key": self._key, "X-Goog-FieldMask": mask}

    async def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = await self._client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise ProviderError("The places service could not be reached.") from exc
        if response.status_code == 429:
            raise ProviderError("The places service is rate limited. Please try again shortly.", status_code=503)
        if response.status_code == 404:
            return {}
        if response.status_code >= 400:
            log.warning("google places error status=%s", response.status_code)
            raise ProviderError("The places service returned an error.")
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderError("The places service returned an unreadable response.") from exc
        return data if isinstance(data, dict) else {}

    async def search(self, query: str, *, near: str | None = None, lat: float | None = None,
                     lng: float | None = None, category: str | None = None, limit: int = 10) -> PlaceSearchResult:
        text = query.strip()
        if category and category in CATEGORY_QUERY and CATEGORY_QUERY[category] not in text.lower():
            text = f"{CATEGORY_QUERY[category]} {text}".strip()
        if near and near.lower() not in text.lower():
            text = f"{text} in {near}".strip()
        body: dict[str, Any] = {"textQuery": text[:300], "languageCode": self._language,
                                "maxResultCount": max(1, min(limit, 20))}
        if lat is not None and lng is not None:
            body["locationBias"] = {"circle": {"center": {"latitude": lat, "longitude": lng}, "radius": 30000.0}}
        data = await self._request("POST", f"{BASE}/places:searchText", json=body,
                                   headers=self._headers(SEARCH_MASK))
        places = [p for p in (map_place(r, near) for r in (data.get("places") or []) if isinstance(r, dict)) if p]
        return PlaceSearchResult(query=text, places=places, provider=self.name, data_origin="live",
                                 notice=None if places else "No places matched this search.")

    async def details(self, place_id: str) -> Place | None:
        if not PLACE_ID_RE.match(place_id):
            return None
        data = await self._request("GET", f"{BASE}/places/{place_id}", headers=self._headers(DETAILS_MASK),
                                   params={"languageCode": self._language})
        return map_place(data) if data else None

    async def photo_uri(self, photo_name: str, max_width: int = 800) -> str | None:
        if not PHOTO_NAME_RE.match(photo_name):
            return None
        data = await self._request(
            "GET", f"{BASE}/{photo_name}/media",
            params={"maxWidthPx": max(100, min(max_width, 1600)), "skipHttpRedirect": "true", "key": self._key},
        )
        uri = data.get("photoUri")
        return uri if isinstance(uri, str) and uri.startswith("https://") else None
