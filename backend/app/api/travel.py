"""Places, routes, transport and itinerary endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import client_id
from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.core.rate_limit import rate_limit
from app.db.session import get_session
from app.nlp.gazetteer import get_destination
from app.schemas.itinerary import ItineraryOut, ItineraryPatch, ItineraryRequest, ItinerarySummary
from app.schemas.travel import Place, PlaceSearchResult, RouteRequest, RouteResult, TransportInfo
from app.services import itinerary_service as its
from app.services.container import Container, get_container

router = APIRouter(prefix="/api", tags=["travel"])
provider_limit = rate_limit("providers", lambda: get_settings().rate_limit_providers_per_minute, 60)
CATEGORIES = "^(tourist_attraction|lodging|restaurant|cafe|museum|temple|beach|park|shopping)$"


@router.get("/places/search", response_model=PlaceSearchResult, dependencies=[Depends(provider_limit)])
async def search_places(q: str = Query("", max_length=200), near: str | None = Query(None, max_length=100),
                        category: str | None = Query(None, pattern=CATEGORIES),
                        limit: int = Query(10, ge=1, le=20),
                        c: Container = Depends(get_container)) -> PlaceSearchResult:
    d = get_destination(near) if near else None
    return await c.places.search(q or (near or ""), near=d.name if d else near, lat=d.lat if d else None,
                                 lng=d.lng if d else None, category=category, limit=limit)


@router.get("/places/photo", dependencies=[Depends(provider_limit)],
            summary="Redirect to a short-lived provider photo URL (keeps the API key server-side)")
async def place_photo(name: str = Query(..., max_length=500), w: int = Query(800, ge=100, le=1600),
                      c: Container = Depends(get_container)) -> RedirectResponse:
    uri = await c.places.photo_uri(name, w)
    if not uri:
        raise NotFoundError("Photo not available.")
    return RedirectResponse(uri, status_code=302, headers={"Cache-Control": "private, max-age=300"})


@router.get("/places/{place_id}", response_model=Place, dependencies=[Depends(provider_limit)])
async def place_details(place_id: str, c: Container = Depends(get_container)) -> Place:
    place = await c.places.details(place_id)
    if place is None:
        raise NotFoundError("Place not found.")
    return place


@router.post("/routes", response_model=RouteResult, dependencies=[Depends(provider_limit)],
             summary="Compute a route (road distance/duration only from a configured routing provider)")
async def compute_route(body: RouteRequest, c: Container = Depends(get_container)) -> RouteResult:
    return await c.routes.compute(body)


@router.get("/transport", response_model=TransportInfo)
async def transport_info(mode: str | None = Query(None, pattern="^(TRAIN|BUS|FLIGHT)$"),
                         origin: str | None = Query(None, max_length=100),
                         destination: str | None = Query(None, max_length=100),
                         c: Container = Depends(get_container)) -> TransportInfo:
    return await c.transport.lookup(mode=mode, origin=origin, destination=destination)


@router.post("/itineraries", response_model=ItineraryOut, status_code=201, dependencies=[Depends(provider_limit)])
async def create_itinerary(body: ItineraryRequest, cid: str = Depends(client_id), c: Container = Depends(get_container),
                           session: AsyncSession = Depends(get_session)) -> ItineraryOut:
    return its.to_out(await its.create_itinerary(session, c.places, cid, body))


@router.get("/itineraries", response_model=list[ItinerarySummary])
async def list_itineraries(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                           cid: str = Depends(client_id),
                           session: AsyncSession = Depends(get_session)) -> list[ItinerarySummary]:
    return [its.summary(r) for r in await its.list_itineraries(session, cid, limit, offset)]


@router.get("/itineraries/{itinerary_id}", response_model=ItineraryOut)
async def get_itinerary(itinerary_id: str, cid: str = Depends(client_id),
                        session: AsyncSession = Depends(get_session)) -> ItineraryOut:
    return its.to_out(await its.get_owned(session, cid, itinerary_id))


@router.patch("/itineraries/{itinerary_id}", response_model=ItineraryOut,
              summary="Apply edit operations (add/remove/move/replace stops, add/remove/regenerate days, preferences)")
async def patch_itinerary(itinerary_id: str, body: ItineraryPatch, cid: str = Depends(client_id),
                          c: Container = Depends(get_container),
                          session: AsyncSession = Depends(get_session)) -> ItineraryOut:
    row = await its.get_owned(session, cid, itinerary_id)
    await its.apply_operations(session, c.places, row, body.operations, body.expected_version)
    return its.to_out(row)


@router.delete("/itineraries/{itinerary_id}", status_code=204, response_class=Response)
async def delete_itinerary(itinerary_id: str, cid: str = Depends(client_id),
                           session: AsyncSession = Depends(get_session)) -> Response:
    row = await its.get_owned(session, cid, itinerary_id)
    await session.delete(row)
    await session.commit()
    return Response(status_code=204)
