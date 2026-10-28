"""Normalized schemas for places, routes and transport. Provider payloads are never passed through raw."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DataOrigin = Literal["live", "demo"]
TravelMode = Literal["DRIVE", "WALK", "BICYCLE", "TWO_WHEELER", "TRANSIT"]


class Attribution(BaseModel):
    name: str
    uri: str | None = None


class PhotoRef(BaseModel):
    # Relative URL on *our* API (proxied so provider keys never reach the browser).
    url: str
    width: int | None = None
    height: int | None = None
    attributions: list[Attribution] = Field(default_factory=list)


class Place(BaseModel):
    id: str
    name: str
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    category: str | None = None
    types: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    rating: float | None = None
    user_rating_count: int | None = None
    price_level: str | None = None
    opening_hours: list[str] = Field(default_factory=list)
    open_now: bool | None = None
    photos: list[PhotoRef] = Field(default_factory=list)
    maps_url: str | None = None
    website: str | None = None
    destination: str | None = None
    # Assumed time on site for planning; labelled as an assumption in the UI.
    typical_visit_minutes: int | None = None
    data_origin: DataOrigin
    provider: str
    provider_attribution: str | None = None


class PlaceSearchResult(BaseModel):
    query: str
    places: list[Place]
    provider: str
    data_origin: DataOrigin
    notice: str | None = None


class RouteLeg(BaseModel):
    start: str
    end: str
    distance_meters: int | None = None
    duration_seconds: int | None = None


class RouteRequest(BaseModel):
    origin: str = Field(min_length=2, max_length=200)
    destination: str = Field(min_length=2, max_length=200)
    stops: list[str] = Field(default_factory=list, max_length=8)
    travel_mode: TravelMode = "DRIVE"


class RouteResult(BaseModel):
    available: bool
    provider: str
    travel_mode: TravelMode
    origin: str
    destination: str
    stops: list[str] = Field(default_factory=list)
    distance_meters: int | None = None
    duration_seconds: int | None = None
    summary: str | None = None
    legs: list[RouteLeg] = Field(default_factory=list)
    polyline: str | None = None
    warnings: list[str] = Field(default_factory=list)
    # Only set when no routing provider is available. Explicitly NOT a road distance.
    straight_line_km: float | None = None
    notice: str | None = None
    retrieved_at: datetime | None = None


class OfficialLink(BaseModel):
    label: str
    url: str


class TransportInfo(BaseModel):
    provider: str
    available: bool
    mode: str | None = None
    origin: str | None = None
    destination: str | None = None
    message: str
    official_links: list[OfficialLink] = Field(default_factory=list)
