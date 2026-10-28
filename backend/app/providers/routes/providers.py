"""Routing providers.

GoogleRoutesProvider returns provider-computed road distance and duration.
NoRoutesProvider never fabricates road values: it explains the limitation and, when both
endpoints are known places, gives a straight-line distance that the UI labels as such.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx

from app.core.errors import ProviderError
from app.core.logging import get_logger
from app.nlp.gazetteer import get_destination, haversine_km
from app.schemas.travel import RouteLeg, RouteRequest, RouteResult

log = get_logger(__name__)
ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
FIELD_MASK = ("routes.distanceMeters,routes.duration,routes.description,routes.polyline.encodedPolyline,"
              "routes.legs.distanceMeters,routes.legs.duration,routes.warnings")


class RoutesProvider(Protocol):
    name: str
    is_live: bool

    async def compute(self, request: RouteRequest) -> RouteResult: ...


def _seconds(value: Any) -> int | None:
    if isinstance(value, str) and (m := re.fullmatch(r"(\d+(?:\.\d+)?)s", value)):
        return int(float(m.group(1)))
    return None


class GoogleRoutesProvider:
    name = "google_routes"
    is_live = True

    def __init__(self, api_key: str, timeout: float = 10.0, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._key = api_key
        self._client = httpx.AsyncClient(timeout=timeout, transport=transport, trust_env=False)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def compute(self, request: RouteRequest) -> RouteResult:
        mode = request.travel_mode
        stops = request.stops if mode != "TRANSIT" else []  # Routes API: no intermediates for transit
        body: dict[str, Any] = {
            "origin": {"address": request.origin},
            "destination": {"address": request.destination},
            "intermediates": [{"address": s} for s in stops],
            "travelMode": mode,
            "units": "METRIC",
            "languageCode": "en",
        }
        if mode in ("DRIVE", "TWO_WHEELER"):
            body["routingPreference"] = "TRAFFIC_UNAWARE"
        try:
            response = await self._client.post(ROUTES_URL, json=body,
                                               headers={"X-Goog-Api-Key": self._key, "X-Goog-FieldMask": FIELD_MASK})
        except httpx.HTTPError as exc:
            raise ProviderError("The routing service could not be reached.") from exc
        if response.status_code == 429:
            raise ProviderError("The routing service is rate limited. Please try again shortly.", status_code=503)
        if response.status_code >= 400:
            log.warning("google routes error status=%s", response.status_code)
            raise ProviderError("The routing service could not compute this route.")
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderError("The routing service returned an unreadable response.") from exc
        routes = data.get("routes") or []
        base = RouteResult(available=False, provider=self.name, travel_mode=mode, origin=request.origin,
                           destination=request.destination, stops=stops, retrieved_at=datetime.now(UTC))
        if not routes:
            base.notice = "The routing service found no route between these places for this travel mode."
            return base
        r = routes[0]
        points = [request.origin, *stops, request.destination]
        legs = [
            RouteLeg(start=points[i], end=points[i + 1], distance_meters=leg.get("distanceMeters"),
                     duration_seconds=_seconds(leg.get("duration")))
            for i, leg in enumerate(r.get("legs") or []) if i + 1 < len(points)
        ]
        warnings = [w for w in (r.get("warnings") or []) if isinstance(w, str)]
        if mode == "TRANSIT" and request.stops:
            warnings.append("Intermediate stops are not supported for transit routes and were ignored.")
        return base.model_copy(update={
            "available": True,
            "distance_meters": r.get("distanceMeters"),
            "duration_seconds": _seconds(r.get("duration")),
            "summary": r.get("description"),
            "legs": legs,
            "polyline": (r.get("polyline") or {}).get("encodedPolyline"),
            "warnings": warnings,
        })


class NoRoutesProvider:
    name = "none"
    is_live = False

    async def compute(self, request: RouteRequest) -> RouteResult:
        a, b = get_destination(request.origin), get_destination(request.destination)
        straight = round(haversine_km((a.lat, a.lng), (b.lat, b.lng))) if a and b and a != b else None
        notice = ("Road distance and travel time need a routing provider (set GOOGLE_MAPS_API_KEY with the Routes "
                  "API enabled). ")
        if straight is not None:
            notice += (f"For orientation only: the straight-line distance between the city centres is about "
                       f"{straight} km. Roads are usually considerably longer, so do not use this for planning "
                       f"drive times.")
        return RouteResult(available=False, provider=self.name, travel_mode=request.travel_mode,
                           origin=request.origin, destination=request.destination, stops=request.stops,
                           straight_line_km=straight, notice=notice)
