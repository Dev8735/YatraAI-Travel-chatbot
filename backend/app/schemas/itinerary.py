"""Itinerary request/plan/edit schemas."""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.schemas.nlp import Money
from app.schemas.travel import Place

Pace = Literal["relaxed", "balanced", "packed"]
BudgetTier = Literal["budget", "mid", "luxury"]


class ItineraryRequest(BaseModel):
    destination: str = Field(min_length=2, max_length=100)
    origin: str | None = Field(default=None, max_length=100)
    start_date: dt.date | None = None
    days: int = Field(ge=1, le=14)
    travellers: int | None = Field(default=None, ge=1, le=50)
    budget: Money | None = None
    budget_level: BudgetTier | None = None
    interests: list[str] = Field(default_factory=list, max_length=12)
    pace: Pace = "balanced"
    transport_mode: str | None = Field(default=None, max_length=20)
    accommodation: list[str] = Field(default_factory=list, max_length=6)
    accessibility: list[str] = Field(default_factory=list, max_length=6)


class Stop(BaseModel):
    id: str
    place: Place
    start_time: str
    end_time: str
    duration_minutes: int
    transfer_minutes_before: int | None = None
    transfer_is_estimate: bool = True
    reason: str
    notes: list[str] = Field(default_factory=list)
    hours_verified: bool = False


class Break(BaseModel):
    time: str
    label: str
    duration_minutes: int


class Day(BaseModel):
    day: int
    date: dt.date | None = None
    title: str
    stops: list[Stop] = Field(default_factory=list)
    breaks: list[Break] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class BudgetEstimate(BaseModel):
    tier: BudgetTier
    currency: str = "INR"
    per_person_per_day_min: int
    per_person_per_day_max: int
    days: int
    travellers: int
    travellers_assumed: bool
    total_min: int
    total_max: int
    user_budget: Money | None = None
    within_user_budget: Literal["yes", "no", "partly", "unknown"] = "unknown"
    basis: str
    excludes: list[str] = Field(default_factory=list)
    source_url: str | None = None


class ItineraryPlan(BaseModel):
    destination: str
    days: list[Day]
    unplaced: list[Place] = Field(default_factory=list)
    excluded_place_ids: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    budget_estimate: BudgetEstimate | None = None
    data_origin: Literal["live", "demo"]
    provider: str
    generated_at: dt.datetime


class ItineraryOut(BaseModel):
    id: str
    title: str
    conversation_id: str | None
    request: ItineraryRequest
    plan: ItineraryPlan
    version: int
    created_at: dt.datetime
    updated_at: dt.datetime


class ItinerarySummary(BaseModel):
    id: str
    title: str
    destination: str
    days: int
    version: int
    updated_at: dt.datetime


# --- PATCH operations -------------------------------------------------------
class RemoveStop(BaseModel):
    op: Literal["remove_stop"]
    stop_id: str


class AddStop(BaseModel):
    op: Literal["add_stop"]
    day: int = Field(ge=1)
    place_id: str


class MoveStop(BaseModel):
    op: Literal["move_stop"]
    stop_id: str
    to_day: int = Field(ge=1)
    position: int | None = Field(default=None, ge=0)


class ReplaceStop(BaseModel):
    op: Literal["replace_stop"]
    stop_id: str
    place_id: str


class AddDay(BaseModel):
    op: Literal["add_day"]


class RemoveDay(BaseModel):
    op: Literal["remove_day"]
    day: int = Field(ge=1)


class RegenerateDay(BaseModel):
    op: Literal["regenerate_day"]
    day: int = Field(ge=1)


class UpdatePreferences(BaseModel):
    op: Literal["update_preferences"]
    pace: Pace | None = None
    interests: list[str] | None = None
    budget_level: BudgetTier | None = None
    travellers: int | None = Field(default=None, ge=1, le=50)
    start_date: dt.date | None = None


class Rename(BaseModel):
    op: Literal["rename"]
    title: str = Field(min_length=1, max_length=200)


ItineraryOperation = Annotated[
    RemoveStop | AddStop | MoveStop | ReplaceStop | AddDay | RemoveDay | RegenerateDay | UpdatePreferences | Rename,
    Field(discriminator="op"),
]


class ItineraryPatch(BaseModel):
    operations: list[ItineraryOperation] = Field(min_length=1, max_length=20)
    expected_version: int | None = None
